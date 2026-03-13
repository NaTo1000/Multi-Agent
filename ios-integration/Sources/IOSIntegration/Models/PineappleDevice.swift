import Foundation

/// Represents a WiFi Pineapple device reachable on the local network.
public struct PineappleDevice: Codable, Identifiable, Sendable {
    public var id: String { host }
    public var host: String
    /// REST API key used in the `Authorization` header.
    public var apiKey: String
    /// Names of currently installed/enabled modules.
    public var modules: [String]
    /// Latest recon scan data pulled from the Pineapple.
    public var reconData: [NetworkScan]

    private enum CodingKeys: String, CodingKey {
        case host
        case apiKey    = "api_key"
        case modules
        case reconData = "recon_data"
    }

    public init(
        host: String,
        apiKey: String,
        modules: [String] = [],
        reconData: [NetworkScan] = []
    ) {
        self.host = host
        self.apiKey = apiKey
        self.modules = modules
        self.reconData = reconData
    }
}

/// Describes an installed module on the WiFi Pineapple.
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

    public init(
        id: String,
        name: String,
        isEnabled: Bool,
        version: String? = nil,
        description: String? = nil
    ) {
        self.id = id
        self.name = name
        self.isEnabled = isEnabled
        self.version = version
        self.description = description
    }
}
