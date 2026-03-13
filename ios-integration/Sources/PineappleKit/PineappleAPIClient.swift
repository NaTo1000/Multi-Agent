import Foundation

// MARK: - Protocol

public protocol PineappleAPIClientProtocol: Sendable {
    func listModules() async throws -> [PineappleModule]
    func enableModule(_ name: String) async throws
    func disableModule(_ name: String) async throws
    func getReconData() async throws -> [NetworkScan]
    func configurePineAP(ssid: String, deauth: Bool, harvesting: Bool) async throws
    func executePayload(script: String) async throws
}

// MARK: - Error

public enum PineappleError: Error, LocalizedError, Sendable {
    case invalidHost(String)
    case missingAPIKey
    case networkFailure(underlying: Error)
    case httpError(statusCode: Int, body: String)
    case decodingFailure(underlying: Error)
    case unauthorized

    public var errorDescription: String? {
        switch self {
        case .invalidHost(let h):      return "Invalid Pineapple host: \(h)"
        case .missingAPIKey:           return "Pineapple API key is not set. Open Settings → WiFi Pineapple and enter your API key."
        case .networkFailure(let e):   return "Network failure: \(e.localizedDescription)"
        case .httpError(let c, let b): return "HTTP \(c): \(b)"
        case .decodingFailure(let e):  return "Decoding failed: \(e.localizedDescription)"
        case .unauthorized:            return "Pineapple API key rejected (401)."
        }
    }
}

// MARK: - Supporting types

public struct PineappleModule: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let isEnabled: Bool
    public let version: String?
    public let description: String?

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case isEnabled  = "is_enabled"
        case version
        case description
    }

    public init(id: String, name: String, isEnabled: Bool,
                version: String? = nil, description: String? = nil) {
        self.id = id; self.name = name; self.isEnabled = isEnabled
        self.version = version; self.description = description
    }
}

public struct NetworkScan: Codable, Identifiable, Sendable {
    public var id: String { bssid }
    public let ssid: String
    public let bssid: String
    public let channel: Int
    public let signal: Int
    public let encryption: String
    public let clients: [String]
    public let lastSeen: Date?

    private enum CodingKeys: String, CodingKey {
        case ssid, bssid, channel, signal, encryption, clients
        case lastSeen = "last_seen"
    }

    public init(ssid: String, bssid: String, channel: Int, signal: Int,
                encryption: String = "UNKNOWN", clients: [String] = [], lastSeen: Date? = nil) {
        self.ssid = ssid; self.bssid = bssid; self.channel = channel
        self.signal = signal; self.encryption = encryption
        self.clients = clients; self.lastSeen = lastSeen
    }
}

// MARK: - Actor implementation

/// REST client for the WiFi Pineapple management API.
public actor PineappleAPIClient: PineappleAPIClientProtocol {

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    private var baseURL: URL {
        get throws {
            let host = AppConfig.shared.pineappleHost
            guard let url = URL(string: "http://\(host)/api/v1") else {
                throw PineappleError.invalidHost(host)
            }
            return url
        }
    }

    private var apiKey: String {
        get throws {
            guard let key = KeychainHelper.shared.read(key: KeychainHelper.pineappleKeyKey),
                  !key.isEmpty else {
                throw PineappleError.missingAPIKey
            }
            return key
        }
    }

    public init(session: URLSession = .shared) {
        self.session = session
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Modules

    public func listModules() async throws -> [PineappleModule] {
        let data = try await get(path: "/modules")
        return try decoder.decode([PineappleModule].self, from: data)
    }

    public func enableModule(_ name: String) async throws {
        _ = try await post(path: "/modules/\(name)/enable", body: nil)
    }

    public func disableModule(_ name: String) async throws {
        _ = try await post(path: "/modules/\(name)/disable", body: nil)
    }

    // MARK: - Recon

    public func getReconData() async throws -> [NetworkScan] {
        _ = try await post(path: "/recon/start", body: nil)
        try await Task.sleep(for: .seconds(5))
        let data = try await get(path: "/recon/results")
        return try decoder.decode([NetworkScan].self, from: data)
    }

    // MARK: - PineAP

    public func configurePineAP(ssid: String, deauth: Bool, harvesting: Bool) async throws {
        let payload: [String: Any] = [
            "ssid": ssid,
            "deauth": deauth,
            "harvesting": harvesting
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await post(path: "/pineap/configure", body: body)
    }

    // MARK: - Payloads

    public func executePayload(script: String) async throws {
        let payload: [String: String] = ["script": script]
        let body = try encoder.encode(payload)
        _ = try await post(path: "/payloads/execute", body: body)
    }

    // MARK: - Private HTTP helpers

    private func get(path: String) async throws -> Data {
        let url = try baseURL.appendingPathComponent(path)
        var req = URLRequest(url: url)
        req.setValue(try apiKey, forHTTPHeaderField: "Authorization")
        return try await execute(req)
    }

    private func post(path: String, body: Data?) async throws -> Data {
        let url = try baseURL.appendingPathComponent(path)
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue(try apiKey, forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = body
        return try await execute(req)
    }

    private func execute(_ req: URLRequest) async throws -> Data {
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw PineappleError.networkFailure(underlying: error)
        }
        guard let http = response as? HTTPURLResponse else { throw PineappleError.networkFailure(underlying: URLError(.badServerResponse)) }
        switch http.statusCode {
        case 200...299: return data
        case 401:       throw PineappleError.unauthorized
        default:
            throw PineappleError.httpError(
                statusCode: http.statusCode,
                body: String(data: data, encoding: .utf8) ?? ""
            )
        }
    }
}

// MARK: - KeychainHelper (PineappleKit standalone Keychain access via Security framework)

import Security

private enum KeychainHelper {
    static let pineappleKeyKey = "multiagent.pineapple_api_key"

    /// Reads a string value from the Keychain for the given key.
    static func read(key: String) -> String? {
        let query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: key,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }
        return value
    }
}

private enum AppConfig {
    static let pineappleHost: String = ProcessInfo.processInfo.environment["PINEAPPLE_HOST"] ?? "172.16.42.1"
}
