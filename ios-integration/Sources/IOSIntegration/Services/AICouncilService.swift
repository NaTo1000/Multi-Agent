import Foundation

// MARK: - Error type

/// Errors surfaced by `AICouncilService` and its sub-clients.
public enum AICouncilError: Error, LocalizedError, Sendable {
    case missingCredentials(service: String)
    case httpError(statusCode: Int, body: String)
    case decodingFailure(underlying: Error)
    case networkFailure(underlying: Error)
    case iamTokenFetchFailed
    case emptyResponse
    case unknown

    public var errorDescription: String? {
        switch self {
        case .missingCredentials(let svc):
            return "Missing API credentials for \(svc). Configure in Settings."
        case .httpError(let code, let body):
            return "HTTP \(code): \(body)"
        case .decodingFailure(let err):
            return "Response decoding failed: \(err.localizedDescription)"
        case .networkFailure(let err):
            return "Network error: \(err.localizedDescription)"
        case .iamTokenFetchFailed:
            return "Failed to obtain IBM Cloud IAM access token."
        case .emptyResponse:
            return "The AI service returned an empty response."
        case .unknown:
            return "An unknown AI council error occurred."
        }
    }
}

// MARK: - Protocol

/// Contract for the AI council — any client that can analyse metrics and return recommendations.
public protocol AICouncilServiceProtocol: Sendable {
    /// Analyse the provided telemetry snapshots and return a structured analysis.
    func analyse(
        telemetry: [TelemetryData],
        devices: [Device]
    ) async throws -> AICouncilAnalysis

    /// Run inference on the HuggingFace Inference API.
    func queryHuggingFace(prompt: String) async throws -> String

    /// Run inference via IBM WatsonX.ai.
    func queryWatsonX(prompt: String) async throws -> String
}

// MARK: - Actor implementation

/// `AICouncilService` orchestrates both the **HuggingFace Inference API** and
/// **IBM WatsonX.ai** to analyse live telemetry metrics from the ESP32 fleet.
///
/// Usage:
/// ```swift
/// let council = AICouncilService()
/// let analysis = try await council.analyse(telemetry: frames, devices: devices)
/// ```
public actor AICouncilService: AICouncilServiceProtocol {

    // MARK: - Private state

    private let aiConfig: AIConfig
    private let appConfig: AppConfig
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    /// Number of recent telemetry frames to include in the metrics snapshot window.
    /// 20 frames at 1 Hz gives a ~20-second moving average, which is responsive
    /// enough for real-time alerts while smoothing transient spikes.
    private let metricsSnapshotWindow = 20

    /// Cached IBM Cloud IAM token and its expiry timestamp (unix seconds).
    private var iamToken: String?
    private var iamTokenExpiry: Int = 0

    // MARK: - Init

    public init(aiConfig: AIConfig = .shared, appConfig: AppConfig = .shared) {
        self.aiConfig = aiConfig
        self.appConfig = appConfig

        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 60
        cfg.timeoutIntervalForResource = 120
        self.session = URLSession(configuration: cfg)

        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Public API

    /// Analyses the last N telemetry frames from the fleet, combining insights from
    /// HuggingFace and WatsonX into a single `AICouncilAnalysis`.
    public func analyse(
        telemetry: [TelemetryData],
        devices: [Device]
    ) async throws -> AICouncilAnalysis {

        let snapshot = buildMetricsSnapshot(telemetry: telemetry)
        let context  = buildContextPrompt(telemetry: telemetry, devices: devices, snapshot: snapshot)

        // Run both cloud models concurrently in parallel tasks where credentials are available
        let hfTask: Task<String, Error>? = hfAvailable
            ? Task { try await self.queryHuggingFace(prompt: context) }
            : nil
        let wxTask: Task<String, Error>? = wxAvailable
            ? Task { try await self.queryWatsonX(prompt: context) }
            : nil

        var recommendations: [AIRecommendation] = []
        var summaryParts: [String] = []

        if let task = hfTask {
            do {
                let hfText = try await task.value
                if !hfText.isEmpty {
                    let recs = parseRecommendations(from: hfText, source: .huggingFace, snapshot: snapshot, devices: devices)
                    recommendations.append(contentsOf: recs)
                    summaryParts.append("[HuggingFace] \(hfText.prefix(200))")
                }
            } catch {
                AppLogger.ai.warning("HuggingFace query failed: \(error.localizedDescription)")
            }
        }

        if let task = wxTask {
            do {
                let wxText = try await task.value
                if !wxText.isEmpty {
                    let recs = parseRecommendations(from: wxText, source: .watsonX, snapshot: snapshot, devices: devices)
                    recommendations.append(contentsOf: recs)
                    summaryParts.append("[WatsonX] \(wxText.prefix(200))")
                }
            } catch {
                AppLogger.ai.warning("WatsonX query failed: \(error.localizedDescription)")
            }
        }

        // Always add local heuristic-based recommendations
        recommendations.append(contentsOf: localHeuristics(snapshot: snapshot, devices: devices))

        let summary = summaryParts.isEmpty
            ? buildLocalSummary(snapshot: snapshot, devices: devices)
            : summaryParts.joined(separator: "\n\n")

        return AICouncilAnalysis(
            recommendations: recommendations,
            summaryText: summary,
            metricsSnapshot: snapshot
        )
    }

    /// Posts a prompt to the HuggingFace Inference API and returns the generated text.
    public func queryHuggingFace(prompt: String) async throws -> String {
        guard let token = aiConfig.hfToken, !token.isEmpty else {
            throw AICouncilError.missingCredentials(service: "HuggingFace")
        }

        let params = HFParameters(
            maxNewTokens: aiConfig.maxNewTokens,
            temperature: aiConfig.temperature
        )
        let body = HFGenerationRequest(inputs: prompt, parameters: params)
        let bodyData = try encoder.encode(body)

        var request = URLRequest(url: aiConfig.hfInferenceURL)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json",  forHTTPHeaderField: "Content-Type")
        request.httpBody = bodyData

        let data = try await perform(request: request, service: "HuggingFace")

        let results = try decoder.decode([HFGenerationResult].self, from: data)
        guard let first = results.first else { throw AICouncilError.emptyResponse }
        return first.generatedText
    }

    /// Posts a prompt to IBM WatsonX.ai and returns the generated text.
    public func queryWatsonX(prompt: String) async throws -> String {
        guard let apiKey = aiConfig.watsonXAPIKey, !apiKey.isEmpty,
              let projectID = aiConfig.watsonXProjectID, !projectID.isEmpty else {
            throw AICouncilError.missingCredentials(service: "WatsonX")
        }

        let bearerToken = try await fetchIAMToken(apiKey: apiKey)

        let params = WatsonXParameters(
            maxNewTokens: aiConfig.maxNewTokens,
            temperature: aiConfig.temperature
        )
        let body = WatsonXRequest(
            modelID: aiConfig.watsonXModelID,
            input: prompt,
            parameters: params,
            projectID: projectID
        )
        let bodyData = try encoder.encode(body)

        var url = URLComponents(url: aiConfig.watsonXGenerationURL, resolvingAgainstBaseURL: true)!
        url.queryItems = [URLQueryItem(name: "version", value: "2024-01-15")]

        var request = URLRequest(url: url.url!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(bearerToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json",       forHTTPHeaderField: "Content-Type")
        request.httpBody = bodyData

        let data = try await perform(request: request, service: "WatsonX")

        let response = try decoder.decode(WatsonXResponse.self, from: data)
        guard let first = response.results.first else { throw AICouncilError.emptyResponse }
        return first.generatedText
    }

    // MARK: - Private helpers

    private var hfAvailable: Bool { !(aiConfig.hfToken?.isEmpty ?? true) }
    private var wxAvailable: Bool {
        !(aiConfig.watsonXAPIKey?.isEmpty ?? true) &&
        !(aiConfig.watsonXProjectID?.isEmpty ?? true)
    }

    /// Fetches or refreshes an IBM Cloud IAM bearer token.
    private func fetchIAMToken(apiKey: String) async throws -> String {
        let now = Int(Date().timeIntervalSince1970)
        if let token = iamToken, now < iamTokenExpiry - 60 {
            return token
        }

        var request = URLRequest(url: AIConfig.ibmIAMTokenURL)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        let body = "grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey&apikey=\(apiKey)"
        request.httpBody = body.data(using: .utf8)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw AICouncilError.iamTokenFetchFailed
        }

        let tokenResponse = try decoder.decode(IAMTokenResponse.self, from: data)
        self.iamToken       = tokenResponse.accessToken
        self.iamTokenExpiry = tokenResponse.expiration
        return tokenResponse.accessToken
    }

    private func perform(request: URLRequest, service: String) async throws -> Data {
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw AICouncilError.networkFailure(underlying: error)
        }
        guard let http = response as? HTTPURLResponse else {
            throw AICouncilError.unknown
        }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw AICouncilError.httpError(statusCode: http.statusCode, body: body)
        }
        return data
    }

    /// Aggregates the most recent telemetry into a flat metric→value map for prompting.
    private func buildMetricsSnapshot(telemetry: [TelemetryData]) -> [String: Double] {
        var counts:  [String: Int]    = [:]
        var sums:    [String: Double] = [:]

        for frame in telemetry.suffix(metricsSnapshotWindow) {
            for (key, value) in frame.metrics {
                sums[key, default: 0] += value
                counts[key, default: 0] += 1
            }
        }

        return sums.reduce(into: [String: Double]()) { result, pair in
            let count = counts[pair.key] ?? 1
            result[pair.key] = pair.value / Double(count)
        }
    }

    /// Builds a concise, structured prompt summarising the fleet state.
    private func buildContextPrompt(
        telemetry: [TelemetryData],
        devices: [Device],
        snapshot: [String: Double]
    ) -> String {
        let onlineCount  = devices.filter { $0.status == .online  }.count
        let offlineCount = devices.filter { $0.status == .offline }.count
        let metricsText  = snapshot.sorted(by: { $0.key < $1.key })
            .map { "  \($0.key): \(String(format: "%.2f", $0.value))" }
            .joined(separator: "\n")

        return """
        You are an AI operations advisor for an ESP32 IoT fleet. Analyse these metrics and provide \
        concise, actionable recommendations. Format each recommendation as:
        [SEVERITY: INFO|WARNING|CRITICAL] <title>
        <explanation>

        Fleet status: \(onlineCount) online, \(offlineCount) offline out of \(devices.count) devices.
        Averaged metrics (last 20 frames):
        \(metricsText.isEmpty ? "  No metrics available." : metricsText)

        Provide up to 5 recommendations sorted by priority.
        """
    }

    /// Parses free-text LLM output into structured `AIRecommendation` objects.
    private func parseRecommendations(
        from text: String,
        source: AIRecommendation.AISource,
        snapshot: [String: Double],
        devices: [Device]
    ) -> [AIRecommendation] {
        var recommendations: [AIRecommendation] = []

        let lines = text.components(separatedBy: "\n")
        var index = 0
        while index < lines.count {
            let line = lines[index].trimmingCharacters(in: .whitespaces)

            // Match lines like: [SEVERITY: WARNING] High CPU usage detected
            guard line.hasPrefix("[SEVERITY:") || line.hasPrefix("[WARNING]") ||
                  line.hasPrefix("[CRITICAL]") || line.hasPrefix("[INFO]") else {
                index += 1
                continue
            }

            let severity: AIRecommendation.AISeverity
            if line.contains("CRITICAL") { severity = .critical }
            else if line.contains("WARNING") { severity = .warning }
            else { severity = .info }

            // Extract title — text after the closing bracket
            let title = extractTitle(from: line)

            // Find the body on the next non-empty, non-header line
            let (body, nextIndex) = extractBody(from: lines, startingAfter: index)
            index = nextIndex

            if !title.isEmpty {
                recommendations.append(AIRecommendation(
                    source: source,
                    severity: severity,
                    title: title,
                    body: body
                ))
            }
            index += 1
        }

        // If the model didn't follow the structured format, wrap the whole response
        if recommendations.isEmpty && !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            recommendations.append(AIRecommendation(
                source: source,
                severity: .info,
                title: "\(source.rawValue) Analysis",
                body: String(text.prefix(500))
            ))
        }

        return recommendations
    }

    /// Extracts the recommendation title from a severity-tagged line.
    private func extractTitle(from line: String) -> String {
        if let endBracket = line.firstIndex(of: "]") {
            return line[line.index(after: endBracket)...]
                .trimmingCharacters(in: .whitespaces)
        }
        return line
    }

    /// Finds the first non-empty, non-header line after `startIndex` to use as body text.
    /// Returns the body string and the line index consumed, or the original `startIndex` if not found.
    private func extractBody(from lines: [String], startingAfter startIndex: Int) -> (String, Int) {
        for j in (startIndex + 1)..<lines.count {
            let candidate = lines[j].trimmingCharacters(in: .whitespaces)
            if !candidate.isEmpty && !candidate.hasPrefix("[") {
                return (candidate, j)
            }
        }
        return ("", startIndex)
    }

    /// Fast, local heuristic rules — no network required.
    private func localHeuristics(
        snapshot: [String: Double],
        devices: [Device]
    ) -> [AIRecommendation] {
        var recs: [AIRecommendation] = []

        // CPU heuristic
        if let cpu = snapshot["cpu"], cpu > 85 {
            recs.append(AIRecommendation(
                source: .local,
                severity: cpu > 95 ? .critical : .warning,
                title: "High CPU utilisation (\(Int(cpu))%)",
                body: "Average fleet CPU is above threshold. Consider load balancing tasks or rescheduling heavy agents.",
                metricKey: "cpu"
            ))
        }

        // Memory heuristic
        if let heap = snapshot["heap"], heap < 20_000 {
            recs.append(AIRecommendation(
                source: .local,
                severity: heap < 8_000 ? .critical : .warning,
                title: "Low heap memory (\(Int(heap / 1024)) KB free)",
                body: "Fleet heap is critically low. Trigger a fleet-wide restart or reduce concurrent agent workloads.",
                metricKey: "heap"
            ))
        }

        // Offline devices heuristic
        let offlineDevices = devices.filter { $0.status == .offline }
        if offlineDevices.count > 0 {
            let names = offlineDevices.prefix(3).compactMap { $0.name }.joined(separator: ", ")
            recs.append(AIRecommendation(
                source: .local,
                severity: offlineDevices.count > 2 ? .critical : .warning,
                title: "\(offlineDevices.count) device(s) offline",
                body: "Offline: \(names). Check network connectivity and power supply."
            ))
        }

        // Signal strength heuristic
        if let rssi = snapshot["signal_strength"], rssi < -80 {
            recs.append(AIRecommendation(
                source: .local,
                severity: .warning,
                title: "Weak RF signal (\(Int(rssi)) dBm)",
                body: "Average signal is below -80 dBm. Consider relocating access points or antenna upgrades.",
                metricKey: "signal_strength"
            ))
        }

        return recs
    }

    private func buildLocalSummary(snapshot: [String: Double], devices: [Device]) -> String {
        let online = devices.filter { $0.status == .online }.count
        return "Fleet: \(online)/\(devices.count) devices online. " +
               "Avg CPU: \(snapshot["cpu"].map { String(format: "%.1f%%", $0) } ?? "n/a"), " +
               "Heap: \(snapshot["heap"].map { String(format: "%.0f B", $0) } ?? "n/a")."
    }
}
