import Foundation

// MARK: - HuggingFace models

/// A single text-generation request sent to the HuggingFace Inference API.
public struct HFGenerationRequest: Codable, Sendable {
    public let inputs: String
    public let parameters: HFParameters

    public init(inputs: String, parameters: HFParameters) {
        self.inputs = inputs
        self.parameters = parameters
    }
}

/// Sampling parameters for HuggingFace text generation.
public struct HFParameters: Codable, Sendable {
    public let maxNewTokens: Int
    public let temperature: Double
    public let doSample: Bool
    public let returnFullText: Bool

    private enum CodingKeys: String, CodingKey {
        case maxNewTokens    = "max_new_tokens"
        case temperature
        case doSample        = "do_sample"
        case returnFullText  = "return_full_text"
    }

    public init(
        maxNewTokens: Int = 512,
        temperature: Double = 0.3,
        doSample: Bool = true,
        returnFullText: Bool = false
    ) {
        self.maxNewTokens = maxNewTokens
        self.temperature = temperature
        self.doSample = doSample
        self.returnFullText = returnFullText
    }
}

/// A single generation result returned by HuggingFace.
public struct HFGenerationResult: Codable, Sendable {
    public let generatedText: String

    private enum CodingKeys: String, CodingKey {
        case generatedText = "generated_text"
    }
}

// MARK: - WatsonX models

/// IBM WatsonX.ai text generation request body.
public struct WatsonXRequest: Codable, Sendable {
    public let modelID: String
    public let input: String
    public let parameters: WatsonXParameters
    public let projectID: String

    private enum CodingKeys: String, CodingKey {
        case modelID    = "model_id"
        case input
        case parameters
        case projectID  = "project_id"
    }

    public init(modelID: String, input: String, parameters: WatsonXParameters, projectID: String) {
        self.modelID = modelID
        self.input = input
        self.parameters = parameters
        self.projectID = projectID
    }
}

/// WatsonX generation hyperparameters.
public struct WatsonXParameters: Codable, Sendable {
    public let decodingMethod: String
    public let maxNewTokens: Int
    public let minNewTokens: Int
    public let temperature: Double
    public let topK: Int
    public let topP: Double

    private enum CodingKeys: String, CodingKey {
        case decodingMethod = "decoding_method"
        case maxNewTokens   = "max_new_tokens"
        case minNewTokens   = "min_new_tokens"
        case temperature
        case topK           = "top_k"
        case topP           = "top_p"
    }

    public init(
        decodingMethod: String = "sample",
        maxNewTokens: Int = 512,
        minNewTokens: Int = 1,
        temperature: Double = 0.3,
        topK: Int = 50,
        topP: Double = 0.95
    ) {
        self.decodingMethod = decodingMethod
        self.maxNewTokens = maxNewTokens
        self.minNewTokens = minNewTokens
        self.temperature = temperature
        self.topK = topK
        self.topP = topP
    }
}

/// WatsonX text generation response.
public struct WatsonXResponse: Codable, Sendable {
    public let modelID: String
    public let results: [WatsonXResult]

    private enum CodingKeys: String, CodingKey {
        case modelID = "model_id"
        case results
    }
}

/// A single result item inside a `WatsonXResponse`.
public struct WatsonXResult: Codable, Sendable {
    public let generatedText: String
    public let generatedTokenCount: Int
    public let inputTokenCount: Int
    public let stopReason: String

    private enum CodingKeys: String, CodingKey {
        case generatedText       = "generated_text"
        case generatedTokenCount = "generated_token_count"
        case inputTokenCount     = "input_token_count"
        case stopReason          = "stop_reason"
    }
}

/// IBM Cloud IAM token response.
public struct IAMTokenResponse: Codable, Sendable {
    public let accessToken: String
    public let expiration: Int

    private enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case expiration
    }
}

// MARK: - AI Council domain models

/// A structured AI recommendation produced by the AI council.
public struct AIRecommendation: Identifiable, Sendable {
    public let id: UUID
    public let timestamp: Date
    /// The source AI model that produced this recommendation.
    public let source: AISource
    /// Severity / priority of the recommendation.
    public let severity: AISeverity
    /// Short headline (≤ 120 chars).
    public let title: String
    /// Full explanation.
    public let body: String
    /// Optional device ID the recommendation is about.
    public let deviceID: String?
    /// Optional metric key that triggered this recommendation.
    public let metricKey: String?

    public init(
        id: UUID = UUID(),
        timestamp: Date = Date(),
        source: AISource,
        severity: AISeverity,
        title: String,
        body: String,
        deviceID: String? = nil,
        metricKey: String? = nil
    ) {
        self.id = id
        self.timestamp = timestamp
        self.source = source
        self.severity = severity
        self.title = title
        self.body = body
        self.deviceID = deviceID
        self.metricKey = metricKey
    }

    /// Human-readable source label for display.
    public enum AISource: String, Sendable {
        case huggingFace = "HuggingFace"
        case watsonX     = "WatsonX"
        case local       = "On-Device"
    }

    /// Recommendation importance tier.
    public enum AISeverity: String, Sendable, Comparable, CaseIterable {
        case info     = "Info"
        case warning  = "Warning"
        case critical = "Critical"

        public static func < (lhs: AISeverity, rhs: AISeverity) -> Bool {
            let order: [AISeverity] = [.info, .warning, .critical]
            return (order.firstIndex(of: lhs) ?? 0) < (order.firstIndex(of: rhs) ?? 0)
        }
    }
}

/// Aggregated analysis produced by the AI council for one polling cycle.
public struct AICouncilAnalysis: Sendable {
    public let timestamp: Date
    public let recommendations: [AIRecommendation]
    public let summaryText: String
    public let metricsSnapshot: [String: Double]

    public init(
        timestamp: Date = Date(),
        recommendations: [AIRecommendation],
        summaryText: String,
        metricsSnapshot: [String: Double]
    ) {
        self.timestamp = timestamp
        self.recommendations = recommendations
        self.summaryText = summaryText
        self.metricsSnapshot = metricsSnapshot
    }

    /// Returns recommendations sorted by severity (critical first).
    public var sortedRecommendations: [AIRecommendation] {
        recommendations.sorted { $0.severity > $1.severity }
    }

    public var criticalCount: Int { recommendations.filter { $0.severity == .critical }.count }
    public var warningCount:  Int { recommendations.filter { $0.severity == .warning  }.count }
    public var infoCount:     Int { recommendations.filter { $0.severity == .info     }.count }
}
