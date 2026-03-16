import Foundation

/// Configuration for the AI Council layer — HuggingFace Inference API and IBM WatsonX.ai.
///
/// Credentials are read from environment variables at launch and stored / retrieved
/// from the iOS Keychain at runtime.  No secrets are ever hard-coded.
///
/// | Environment Variable              | Purpose                                     |
/// |-----------------------------------|---------------------------------------------|
/// | `HF_API_TOKEN`                    | HuggingFace Inference API bearer token      |
/// | `HF_MODEL_ID`                     | Model ID (default: Mistral-7B-Instruct-v0.3)|
/// | `HF_INFERENCE_BASE_URL`           | HF Inference endpoint base URL              |
/// | `WATSONX_API_KEY`                 | IBM Cloud IAM API key for WatsonX           |
/// | `WATSONX_PROJECT_ID`              | WatsonX project identifier                  |
/// | `WATSONX_BASE_URL`                | WatsonX regional endpoint URL               |
/// | `WATSONX_MODEL_ID`                | WatsonX model (default: granite-13b-instruct)|
/// | `AI_MAX_TOKENS`                   | Max generation tokens (default: 512)        |
/// | `AI_TEMPERATURE`                  | Sampling temperature 0–2 (default: 0.3)     |
public struct AIConfig: Sendable {

    // MARK: - Shared instance

    public static let shared: AIConfig = AIConfig()

    // MARK: - HuggingFace

    /// HuggingFace Inference API base URL.
    public let hfBaseURL: URL

    /// HuggingFace model ID to use for inference.
    public let hfModelID: String

    /// HuggingFace bearer token (loaded from env / Keychain).
    public let hfToken: String?

    // MARK: - WatsonX

    /// IBM WatsonX.ai regional endpoint, e.g. `https://us-south.ml.cloud.ibm.com`.
    public let watsonXBaseURL: URL

    /// WatsonX project identifier.
    public let watsonXProjectID: String?

    /// WatsonX model ID.
    public let watsonXModelID: String

    /// IBM Cloud IAM API key (loaded from env / Keychain).
    public let watsonXAPIKey: String?

    // MARK: - Generation parameters

    /// Maximum number of new tokens to generate.
    public let maxNewTokens: Int

    /// Sampling temperature (0 = greedy, 1 = balanced, 2 = creative).
    public let temperature: Double

    // MARK: - Init

    public init() {
        let env = ProcessInfo.processInfo.environment

        // HuggingFace
        let rawHFBase = env["HF_INFERENCE_BASE_URL"] ?? "https://api-inference.huggingface.co"
        self.hfBaseURL = URL(string: rawHFBase)
            ?? URL(string: "https://api-inference.huggingface.co")!
        self.hfModelID = env["HF_MODEL_ID"]
            ?? "mistralai/Mistral-7B-Instruct-v0.3"
        self.hfToken = env["HF_API_TOKEN"]
            ?? KeychainHelper.shared.read(key: KeychainHelper.hfTokenKey)

        // WatsonX
        let rawWXBase = env["WATSONX_BASE_URL"] ?? "https://us-south.ml.cloud.ibm.com"
        self.watsonXBaseURL = URL(string: rawWXBase)
            ?? URL(string: "https://us-south.ml.cloud.ibm.com")!
        self.watsonXProjectID = env["WATSONX_PROJECT_ID"]
            ?? KeychainHelper.shared.read(key: KeychainHelper.watsonXProjectKey)
        self.watsonXModelID = env["WATSONX_MODEL_ID"]
            ?? "ibm/granite-13b-instruct-v2"
        self.watsonXAPIKey = env["WATSONX_API_KEY"]
            ?? KeychainHelper.shared.read(key: KeychainHelper.watsonXAPIKey)

        // Generation
        if let raw = env["AI_MAX_TOKENS"], let v = Int(raw) {
            self.maxNewTokens = v
        } else {
            self.maxNewTokens = 512
        }
        if let raw = env["AI_TEMPERATURE"], let v = Double(raw) {
            self.temperature = min(max(v, 0), 2)
        } else {
            self.temperature = 0.3
        }
    }

    // MARK: - Derived helpers

    /// HuggingFace Inference URL for the configured model.
    public var hfInferenceURL: URL {
        hfBaseURL.appendingPathComponent("models/\(hfModelID)")
    }

    /// WatsonX text generation endpoint.
    public var watsonXGenerationURL: URL {
        watsonXBaseURL.appendingPathComponent("ml/v1/text/generation")
    }

    /// WatsonX IAM token exchange endpoint.
    public static let ibmIAMTokenURL = URL(string: "https://iam.cloud.ibm.com/identity/token")!
}
