import Foundation

/// Central configuration for the Multi-Agent iOS integration.
/// Values can be overridden via environment variables at launch time,
/// which is useful for CI, TestFlight, and enterprise distributions.
public struct AppConfig: Sendable {

    // MARK: - Shared instance

    /// The shared configuration singleton, initialised once at launch.
    public static let shared: AppConfig = AppConfig()

    // MARK: - Backend

    /// Base URL for the FastAPI REST backend (e.g. "http://192.168.1.10:8000").
    public let baseURL: URL

    /// WebSocket endpoint for live telemetry streaming.
    public let webSocketURL: URL

    // MARK: - Pineapple

    /// Hostname or IP address of the WiFi Pineapple device on the local network.
    public let pineappleHost: String

    // MARK: - Networking

    /// Timeout (seconds) applied to every URLRequest.
    public let requestTimeout: TimeInterval

    /// Maximum number of retry attempts before surfacing an error.
    public let retryMaxAttempts: Int

    /// Base delay (seconds) for the first retry; subsequent retries use exponential back-off.
    public let retryBaseDelay: TimeInterval

    // MARK: - Init

    /// Creates an `AppConfig`, falling back to safe defaults when environment variables
    /// are absent.
    ///
    /// Supported environment variables:
    /// | Variable                   | Default                              |
    /// |----------------------------|--------------------------------------|
    /// | `MULTI_AGENT_BASE_URL`     | `http://localhost:8000`              |
    /// | `MULTI_AGENT_WS_URL`       | `ws://localhost:8000/ws/telemetry`   |
    /// | `PINEAPPLE_HOST`           | `172.16.42.1`                        |
    /// | `REQUEST_TIMEOUT`          | `30`                                 |
    /// | `RETRY_MAX_ATTEMPTS`       | `3`                                  |
    /// | `RETRY_BASE_DELAY`         | `1.0`                                |
    public init() {
        let env = ProcessInfo.processInfo.environment

        let rawBase = env["MULTI_AGENT_BASE_URL"] ?? "http://localhost:8000"
        self.baseURL = URL(string: rawBase)
            ?? URL(string: "http://localhost:8000")!

        let rawWS = env["MULTI_AGENT_WS_URL"] ?? "ws://localhost:8000/ws/telemetry"
        self.webSocketURL = URL(string: rawWS)
            ?? URL(string: "ws://localhost:8000/ws/telemetry")!

        self.pineappleHost = env["PINEAPPLE_HOST"] ?? "172.16.42.1"

        if let raw = env["REQUEST_TIMEOUT"], let parsed = TimeInterval(raw) {
            self.requestTimeout = parsed
        } else {
            self.requestTimeout = 30
        }

        if let raw = env["RETRY_MAX_ATTEMPTS"], let parsed = Int(raw) {
            self.retryMaxAttempts = parsed
        } else {
            self.retryMaxAttempts = 3
        }

        if let raw = env["RETRY_BASE_DELAY"], let parsed = TimeInterval(raw) {
            self.retryBaseDelay = parsed
        } else {
            self.retryBaseDelay = 1.0
        }
    }

    // MARK: - Derived helpers

    /// Constructs a full API URL by appending a path component to `baseURL`.
    public func apiURL(path: String) -> URL {
        baseURL.appendingPathComponent(path)
    }

    /// Returns a `URLSession` pre-configured with `requestTimeout`.
    public func makeSession() -> URLSession {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = requestTimeout
        config.timeoutIntervalForResource = requestTimeout * 4
        return URLSession(configuration: config)
    }
}
