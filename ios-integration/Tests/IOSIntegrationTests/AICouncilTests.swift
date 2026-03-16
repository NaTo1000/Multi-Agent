import XCTest
@testable import IOSIntegration

/// Comprehensive tests for the AI Council layer:
/// - `AICouncilService` local heuristics and prompt building
/// - `AIModels` Codable conformance
/// - `AIConfig` defaults and environment variable parsing
/// - Error type descriptions
final class AICouncilTests: XCTestCase {

    // MARK: - AIConfig defaults

    func testAIConfigDefaultHFBaseURL() {
        let cfg = AIConfig()
        XCTAssertEqual(cfg.hfBaseURL.host, "api-inference.huggingface.co")
    }

    func testAIConfigDefaultWatsonXBaseURL() {
        let cfg = AIConfig()
        XCTAssertEqual(cfg.watsonXBaseURL.host, "us-south.ml.cloud.ibm.com")
    }

    func testAIConfigDefaultModel() {
        let cfg = AIConfig()
        XCTAssertTrue(cfg.hfModelID.contains("Mistral") || !cfg.hfModelID.isEmpty)
    }

    func testAIConfigDefaultWatsonXModel() {
        let cfg = AIConfig()
        XCTAssertTrue(cfg.watsonXModelID.contains("granite") || !cfg.watsonXModelID.isEmpty)
    }

    func testAIConfigDefaultMaxTokens() {
        let cfg = AIConfig()
        XCTAssertGreaterThan(cfg.maxNewTokens, 0)
    }

    func testAIConfigDefaultTemperature() {
        let cfg = AIConfig()
        XCTAssertGreaterThanOrEqual(cfg.temperature, 0)
        XCTAssertLessThanOrEqual(cfg.temperature, 2)
    }

    func testAIConfigDerivedHFInferenceURL() {
        let cfg = AIConfig()
        let url = cfg.hfInferenceURL
        XCTAssertTrue(url.absoluteString.contains("models"))
        XCTAssertTrue(url.absoluteString.contains(cfg.hfModelID))
    }

    func testAIConfigDerivedWatsonXURL() {
        let cfg = AIConfig()
        let url = cfg.watsonXGenerationURL
        XCTAssertTrue(url.absoluteString.contains("text/generation"))
    }

    func testIBMIAMTokenURL() {
        XCTAssertEqual(AIConfig.ibmIAMTokenURL.host, "iam.cloud.ibm.com")
    }

    // MARK: - AICouncilError descriptions

    func testAllErrorsHaveDescriptions() {
        let errors: [AICouncilError] = [
            .missingCredentials(service: "HuggingFace"),
            .httpError(statusCode: 429, body: "rate limited"),
            .decodingFailure(underlying: NSError(domain: "test", code: 1)),
            .networkFailure(underlying: NSError(domain: "test", code: 2)),
            .iamTokenFetchFailed,
            .emptyResponse,
            .unknown,
        ]
        for error in errors {
            XCTAssertNotNil(error.errorDescription, "Missing description for \(error)")
            XCTAssertFalse(error.errorDescription!.isEmpty)
        }
    }

    func testMissingCredentialsErrorContainsServiceName() {
        let error = AICouncilError.missingCredentials(service: "WatsonX")
        XCTAssertTrue(error.errorDescription?.contains("WatsonX") == true)
    }

    func testHTTPErrorContainsStatusCode() {
        let error = AICouncilError.httpError(statusCode: 503, body: "Service Unavailable")
        XCTAssertTrue(error.errorDescription?.contains("503") == true)
    }

    // MARK: - HuggingFace models

    func testHFParametersDefaults() {
        let params = HFParameters()
        XCTAssertEqual(params.maxNewTokens, 512)
        XCTAssertEqual(params.temperature, 0.3, accuracy: 0.001)
        XCTAssertTrue(params.doSample)
        XCTAssertFalse(params.returnFullText)
    }

    func testHFParametersCustomValues() {
        let params = HFParameters(maxNewTokens: 256, temperature: 0.7, doSample: false, returnFullText: true)
        XCTAssertEqual(params.maxNewTokens, 256)
        XCTAssertEqual(params.temperature, 0.7, accuracy: 0.001)
        XCTAssertFalse(params.doSample)
        XCTAssertTrue(params.returnFullText)
    }

    func testHFGenerationRequestEncoding() throws {
        let params = HFParameters(maxNewTokens: 100, temperature: 0.5)
        let req = HFGenerationRequest(inputs: "Test prompt", parameters: params)
        let data = try JSONEncoder().encode(req)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(dict["inputs"] as? String, "Test prompt")
        let paramsDict = dict["parameters"] as? [String: Any]
        XCTAssertNotNil(paramsDict)
        XCTAssertEqual(paramsDict?["max_new_tokens"] as? Int, 100)
    }

    func testHFGenerationResultDecoding() throws {
        let json = """
        [{"generated_text": "This is the AI response."}]
        """.data(using: .utf8)!
        let results = try JSONDecoder().decode([HFGenerationResult].self, from: json)
        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].generatedText, "This is the AI response.")
    }

    func testHFGenerationResultDecodingMultiple() throws {
        let json = """
        [
            {"generated_text": "Response A"},
            {"generated_text": "Response B"}
        ]
        """.data(using: .utf8)!
        let results = try JSONDecoder().decode([HFGenerationResult].self, from: json)
        XCTAssertEqual(results.count, 2)
        XCTAssertEqual(results[1].generatedText, "Response B")
    }

    // MARK: - WatsonX models

    func testWatsonXParametersDefaults() {
        let params = WatsonXParameters()
        XCTAssertEqual(params.decodingMethod, "sample")
        XCTAssertEqual(params.maxNewTokens, 512)
        XCTAssertEqual(params.minNewTokens, 1)
        XCTAssertEqual(params.temperature, 0.3, accuracy: 0.001)
        XCTAssertEqual(params.topK, 50)
        XCTAssertEqual(params.topP, 0.95, accuracy: 0.001)
    }

    func testWatsonXRequestEncoding() throws {
        let params = WatsonXParameters(maxNewTokens: 200)
        let req = WatsonXRequest(
            modelID: "ibm/granite-13b-instruct-v2",
            input: "Analyse this",
            parameters: params,
            projectID: "test-project-id"
        )
        let data = try JSONEncoder().encode(req)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(dict["model_id"] as? String, "ibm/granite-13b-instruct-v2")
        XCTAssertEqual(dict["input"] as? String, "Analyse this")
        XCTAssertEqual(dict["project_id"] as? String, "test-project-id")
    }

    func testWatsonXResponseDecoding() throws {
        let json = """
        {
            "model_id": "ibm/granite-13b-instruct-v2",
            "results": [
                {
                    "generated_text": "The fleet is healthy.",
                    "generated_token_count": 5,
                    "input_token_count": 42,
                    "stop_reason": "eos_token"
                }
            ]
        }
        """.data(using: .utf8)!
        let response = try JSONDecoder().decode(WatsonXResponse.self, from: json)
        XCTAssertEqual(response.modelID, "ibm/granite-13b-instruct-v2")
        XCTAssertEqual(response.results.count, 1)
        XCTAssertEqual(response.results[0].generatedText, "The fleet is healthy.")
        XCTAssertEqual(response.results[0].generatedTokenCount, 5)
        XCTAssertEqual(response.results[0].stopReason, "eos_token")
    }

    func testIAMTokenResponseDecoding() throws {
        let json = """
        {"access_token": "eyJ...", "expiration": 1705312200}
        """.data(using: .utf8)!
        let token = try JSONDecoder().decode(IAMTokenResponse.self, from: json)
        XCTAssertEqual(token.accessToken, "eyJ...")
        XCTAssertEqual(token.expiration, 1705312200)
    }

    // MARK: - AIRecommendation model

    func testAIRecommendationDefaults() {
        let rec = AIRecommendation(
            source: .local,
            severity: .warning,
            title: "High CPU",
            body: "CPU above threshold"
        )
        XCTAssertNotNil(rec.id)
        XCTAssertEqual(rec.source, .local)
        XCTAssertEqual(rec.severity, .warning)
        XCTAssertEqual(rec.title, "High CPU")
        XCTAssertNil(rec.deviceID)
        XCTAssertNil(rec.metricKey)
    }

    func testAIRecommendationWithDeviceAndMetric() {
        let rec = AIRecommendation(
            source: .watsonX,
            severity: .critical,
            title: "Memory critical",
            body: "Heap below 8 KB",
            deviceID: "esp32-01",
            metricKey: "heap"
        )
        XCTAssertEqual(rec.deviceID, "esp32-01")
        XCTAssertEqual(rec.metricKey, "heap")
        XCTAssertEqual(rec.source, .watsonX)
    }

    func testAISeverityOrdering() {
        XCTAssertLessThan(AIRecommendation.AISeverity.info, .warning)
        XCTAssertLessThan(AIRecommendation.AISeverity.warning, .critical)
        XCTAssertGreaterThan(AIRecommendation.AISeverity.critical, .info)
    }

    func testAISeverityAllCases() {
        let cases = AIRecommendation.AISeverity.allCases
        XCTAssertEqual(cases.count, 3)
        XCTAssertTrue(cases.contains(.info))
        XCTAssertTrue(cases.contains(.warning))
        XCTAssertTrue(cases.contains(.critical))
    }

    func testAISourceRawValues() {
        XCTAssertEqual(AIRecommendation.AISource.huggingFace.rawValue, "HuggingFace")
        XCTAssertEqual(AIRecommendation.AISource.watsonX.rawValue, "WatsonX")
        XCTAssertEqual(AIRecommendation.AISource.local.rawValue, "On-Device")
    }

    // MARK: - AICouncilAnalysis

    func testAICouncilAnalysisCounts() {
        let recs: [AIRecommendation] = [
            AIRecommendation(source: .local, severity: .critical, title: "C1", body: ""),
            AIRecommendation(source: .local, severity: .critical, title: "C2", body: ""),
            AIRecommendation(source: .local, severity: .warning,  title: "W1", body: ""),
            AIRecommendation(source: .local, severity: .info,     title: "I1", body: ""),
        ]
        let analysis = AICouncilAnalysis(
            recommendations: recs,
            summaryText: "Test summary",
            metricsSnapshot: [:]
        )
        XCTAssertEqual(analysis.criticalCount, 2)
        XCTAssertEqual(analysis.warningCount, 1)
        XCTAssertEqual(analysis.infoCount, 1)
    }

    func testAICouncilAnalysisSortedRecommendations() {
        let recs: [AIRecommendation] = [
            AIRecommendation(source: .local, severity: .info,     title: "Info",     body: ""),
            AIRecommendation(source: .local, severity: .critical, title: "Critical", body: ""),
            AIRecommendation(source: .local, severity: .warning,  title: "Warning",  body: ""),
        ]
        let analysis = AICouncilAnalysis(
            recommendations: recs,
            summaryText: "",
            metricsSnapshot: [:]
        )
        let sorted = analysis.sortedRecommendations
        XCTAssertEqual(sorted[0].severity, .critical)
        XCTAssertEqual(sorted[1].severity, .warning)
        XCTAssertEqual(sorted[2].severity, .info)
    }

    func testAICouncilAnalysisEmptyRecommendations() {
        let analysis = AICouncilAnalysis(
            recommendations: [],
            summaryText: "All clear",
            metricsSnapshot: ["cpu": 10.0]
        )
        XCTAssertEqual(analysis.criticalCount, 0)
        XCTAssertEqual(analysis.warningCount, 0)
        XCTAssertEqual(analysis.infoCount, 0)
        XCTAssertTrue(analysis.sortedRecommendations.isEmpty)
        XCTAssertEqual(analysis.metricsSnapshot["cpu"], 10.0)
    }

    // MARK: - AICouncilService local heuristics (no network)

    func testLocalHeuristicsHighCPUProducesWarning() async throws {
        let service = AICouncilService()
        let telemetry = (0..<5).map { i in
            TelemetryData(
                timestamp: Date(),
                deviceId: "esp32-0\(i)",
                metrics: ["cpu": 90.0]
            )
        }
        let devices = [Device(id: "esp32-00", name: "Alpha", status: .online, capabilities: [])]
        let analysis = try await service.analyse(telemetry: telemetry, devices: devices)

        let cpuRec = analysis.recommendations.first { $0.metricKey == "cpu" }
        XCTAssertNotNil(cpuRec, "Expected a CPU recommendation for high utilisation")
        XCTAssertGreaterThanOrEqual(cpuRec!.severity, .warning)
    }

    func testLocalHeuristicsCriticalCPUProducesCritical() async throws {
        let service = AICouncilService()
        let telemetry = [TelemetryData(
            timestamp: Date(),
            deviceId: "esp32-01",
            metrics: ["cpu": 98.0]
        )]
        let devices: [Device] = []
        let analysis = try await service.analyse(telemetry: telemetry, devices: devices)
        let cpuRec = analysis.recommendations.first { $0.metricKey == "cpu" }
        XCTAssertEqual(cpuRec?.severity, .critical)
    }

    func testLocalHeuristicsLowHeapProducesWarning() async throws {
        let service = AICouncilService()
        let telemetry = [TelemetryData(
            timestamp: Date(),
            deviceId: "esp32-01",
            metrics: ["heap": 15_000]
        )]
        let analysis = try await service.analyse(telemetry: telemetry, devices: [])
        let heapRec = analysis.recommendations.first { $0.metricKey == "heap" }
        XCTAssertNotNil(heapRec)
        XCTAssertGreaterThanOrEqual(heapRec!.severity, .warning)
    }

    func testLocalHeuristicsCriticalHeapProducesCritical() async throws {
        let service = AICouncilService()
        let telemetry = [TelemetryData(
            timestamp: Date(),
            deviceId: "esp32-01",
            metrics: ["heap": 4_000]
        )]
        let analysis = try await service.analyse(telemetry: telemetry, devices: [])
        let heapRec = analysis.recommendations.first { $0.metricKey == "heap" }
        XCTAssertEqual(heapRec?.severity, .critical)
    }

    func testLocalHeuristicsOfflineDeviceProducesWarning() async throws {
        let service = AICouncilService()
        let devices = [
            Device(id: "d1", name: "Alpha", status: .offline, capabilities: []),
            Device(id: "d2", name: "Beta",  status: .online,  capabilities: []),
        ]
        let analysis = try await service.analyse(telemetry: [], devices: devices)
        let offlineRec = analysis.recommendations.first { $0.title.contains("offline") || $0.title.contains("Offline") }
        XCTAssertNotNil(offlineRec)
    }

    func testLocalHeuristicsWeakSignalProducesWarning() async throws {
        let service = AICouncilService()
        let telemetry = [TelemetryData(
            timestamp: Date(),
            deviceId: "esp32-01",
            metrics: ["signal_strength": -85.0]
        )]
        let analysis = try await service.analyse(telemetry: telemetry, devices: [])
        let signalRec = analysis.recommendations.first { $0.metricKey == "signal_strength" }
        XCTAssertNotNil(signalRec)
    }

    func testAnalysisWithNoTelemetryAndHealthyDevices() async throws {
        let service = AICouncilService()
        let devices = [Device(id: "d1", name: "Alpha", status: .online, capabilities: [])]
        let analysis = try await service.analyse(telemetry: [], devices: devices)
        // Should complete without throwing
        XCTAssertNotNil(analysis)
    }

    func testAnalysisMetricsSnapshotAveraging() async throws {
        let service = AICouncilService()
        // Two frames with cpu 60 and 80 → avg 70
        let telemetry = [
            TelemetryData(timestamp: Date(), deviceId: "d1", metrics: ["cpu": 60]),
            TelemetryData(timestamp: Date(), deviceId: "d1", metrics: ["cpu": 80]),
        ]
        let analysis = try await service.analyse(telemetry: telemetry, devices: [])
        if let cpuAvg = analysis.metricsSnapshot["cpu"] {
            XCTAssertEqual(cpuAvg, 70, accuracy: 1.0)
        }
    }

    // MARK: - queryHuggingFace missing credentials

    func testQueryHuggingFaceMissingTokenThrows() async {
        // Build a config with no token
        let service = AICouncilService(aiConfig: AIConfig(), appConfig: AppConfig())
        // Only test if no HF token is configured in the environment
        if AIConfig().hfToken == nil {
            do {
                _ = try await service.queryHuggingFace(prompt: "test")
                XCTFail("Expected missingCredentials error")
            } catch AICouncilError.missingCredentials {
                // expected
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }

    // MARK: - queryWatsonX missing credentials

    func testQueryWatsonXMissingKeyThrows() async {
        let service = AICouncilService(aiConfig: AIConfig(), appConfig: AppConfig())
        if AIConfig().watsonXAPIKey == nil {
            do {
                _ = try await service.queryWatsonX(prompt: "test")
                XCTFail("Expected missingCredentials error")
            } catch AICouncilError.missingCredentials {
                // expected
            } catch {
                XCTFail("Unexpected error: \(error)")
            }
        }
    }
}
