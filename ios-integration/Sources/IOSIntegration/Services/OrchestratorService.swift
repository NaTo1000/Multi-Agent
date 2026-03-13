import Foundation

// MARK: - Protocol

/// Defines the contract for interacting with the Multi-Agent FastAPI orchestrator.
public protocol OrchestratorServiceProtocol: Sendable {
    func fetchStatus() async throws -> [String: String]
    func fetchDevices() async throws -> [Device]
    func registerDevice(_ device: DeviceCreate) async throws -> Device
    func deleteDevice(id: String) async throws
    func dispatchTask(_ task: TaskRequest) async throws -> TaskResponse
    func fetchTasks() async throws -> [TaskResponse]
}

// MARK: - Error

public enum OrchestratorError: Error, LocalizedError, Sendable {
    case invalidURL(String)
    case networkFailure(underlying: Error)
    case httpError(statusCode: Int, body: String)
    case decodingFailure(underlying: Error)
    case unauthorized
    case maxRetriesExceeded(attempts: Int)
    case unknown

    public var errorDescription: String? {
        switch self {
        case .invalidURL(let path):
            return "Invalid URL constructed from path: \(path)"
        case .networkFailure(let err):
            return "Network failure: \(err.localizedDescription)"
        case .httpError(let code, let body):
            return "HTTP \(code): \(body)"
        case .decodingFailure(let err):
            return "Decoding failed: \(err.localizedDescription)"
        case .unauthorized:
            return "Request unauthorized — check API token in Settings."
        case .maxRetriesExceeded(let n):
            return "Request failed after \(n) attempts."
        case .unknown:
            return "An unknown error occurred."
        }
    }
}

// MARK: - Supporting types

/// Payload for dispatching a task to an agent.
public struct TaskRequest: Codable, Sendable {
    public let agentId: String
    public let action: String
    public let parameters: [String: String]

    private enum CodingKeys: String, CodingKey {
        case agentId    = "agent_id"
        case action
        case parameters
    }

    public init(agentId: String, action: String, parameters: [String: String] = [:]) {
        self.agentId = agentId
        self.action = action
        self.parameters = parameters
    }
}

/// Response from the orchestrator after a task is created or queried.
public struct TaskResponse: Codable, Identifiable, Sendable {
    public let id: String
    public let agentId: String
    public let action: String
    public let status: TaskStatus
    public let createdAt: Date
    public let completedAt: Date?
    public let result: String?

    public enum TaskStatus: String, Codable, Sendable {
        case queued, running, completed, failed, cancelled
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case agentId     = "agent_id"
        case action
        case status
        case createdAt   = "created_at"
        case completedAt = "completed_at"
        case result
    }
}

// MARK: - Actor implementation

/// Concrete implementation of `OrchestratorServiceProtocol` backed by URLSession.
public actor OrchestratorService: OrchestratorServiceProtocol {

    private let config: AppConfig
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(config: AppConfig = .shared) {
        self.config = config
        self.session = config.makeSession()

        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Public API

    public func fetchStatus() async throws -> [String: String] {
        let url = config.baseURL.appendingPathComponent(Endpoints.status)
        let data = try await get(url: url)
        guard let dict = try JSONSerialization.jsonObject(with: data) as? [String: String] else {
            return [:]
        }
        return dict
    }

    public func fetchDevices() async throws -> [Device] {
        let url = config.baseURL.appendingPathComponent(Endpoints.devices)
        let data = try await get(url: url)
        return try decoder.decode([Device].self, from: data)
    }

    public func registerDevice(_ device: DeviceCreate) async throws -> Device {
        let url = config.baseURL.appendingPathComponent(Endpoints.devicesCreate)
        let body = try encoder.encode(device)
        let data = try await post(url: url, body: body)
        return try decoder.decode(Device.self, from: data)
    }

    public func deleteDevice(id: String) async throws {
        let url = config.baseURL.appendingPathComponent(Endpoints.deviceDelete(id: id))
        _ = try await request(url: url, method: "DELETE", body: nil)
    }

    public func dispatchTask(_ task: TaskRequest) async throws -> TaskResponse {
        let url = config.baseURL.appendingPathComponent(Endpoints.tasksCreate)
        let body = try encoder.encode(task)
        let data = try await post(url: url, body: body)
        return try decoder.decode(TaskResponse.self, from: data)
    }

    public func fetchTasks() async throws -> [TaskResponse] {
        let url = config.baseURL.appendingPathComponent(Endpoints.tasks)
        let data = try await get(url: url)
        return try decoder.decode([TaskResponse].self, from: data)
    }

    // MARK: - Private helpers

    private func get(url: URL) async throws -> Data {
        try await withRetry { [self] in
            try await self.request(url: url, method: "GET", body: nil)
        }
    }

    private func post(url: URL, body: Data) async throws -> Data {
        try await withRetry { [self] in
            try await self.request(url: url, method: "POST", body: body)
        }
    }

    private func request(url: URL, method: String, body: Data?) async throws -> Data {
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = KeychainHelper.shared.read(key: KeychainHelper.apiTokenKey) {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            req.httpBody = body
        }

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw OrchestratorError.networkFailure(underlying: error)
        }

        guard let http = response as? HTTPURLResponse else {
            throw OrchestratorError.unknown
        }

        switch http.statusCode {
        case 200...299:
            return data
        case 401:
            throw OrchestratorError.unauthorized
        default:
            let body = String(data: data, encoding: .utf8) ?? ""
            throw OrchestratorError.httpError(statusCode: http.statusCode, body: body)
        }
    }

    /// Retries `operation` with exponential back-off up to `config.retryMaxAttempts` times.
    private func withRetry<T: Sendable>(operation: @Sendable () async throws -> T) async throws -> T {
        var lastError: Error = OrchestratorError.unknown
        for attempt in 0..<config.retryMaxAttempts {
            do {
                return try await operation()
            } catch OrchestratorError.unauthorized {
                throw OrchestratorError.unauthorized   // never retry auth failures
            } catch {
                lastError = error
                if attempt < config.retryMaxAttempts - 1 {
                    let delay = config.retryBaseDelay * pow(2.0, Double(attempt))
                    try await Task.sleep(for: .seconds(delay))
                }
            }
        }
        throw OrchestratorError.maxRetriesExceeded(attempts: config.retryMaxAttempts)
    }
}
