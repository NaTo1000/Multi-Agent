import Foundation

/// Represents a single ESP32 node managed by the Multi-Agent orchestrator.
public struct Device: Codable, Identifiable, Sendable {
    public let id: String
    public var name: String
    public var status: DeviceStatus
    public var firmwareVersion: String?
    public var lastSeen: Date?
    public var ipAddress: String?
    public var macAddress: String?
    public var capabilities: [String]

    public enum DeviceStatus: String, Codable, Sendable {
        case online
        case offline
        case busy
        case error
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case status
        case firmwareVersion  = "firmware_version"
        case lastSeen         = "last_seen"
        case ipAddress        = "ip_address"
        case macAddress       = "mac_address"
        case capabilities
    }

    public init(
        id: String,
        name: String,
        status: DeviceStatus = .offline,
        firmwareVersion: String? = nil,
        lastSeen: Date? = nil,
        ipAddress: String? = nil,
        macAddress: String? = nil,
        capabilities: [String] = []
    ) {
        self.id = id
        self.name = name
        self.status = status
        self.firmwareVersion = firmwareVersion
        self.lastSeen = lastSeen
        self.ipAddress = ipAddress
        self.macAddress = macAddress
        self.capabilities = capabilities
    }
}

/// Payload used when registering a new device with the orchestrator.
public struct DeviceCreate: Codable, Sendable {
    public let name: String
    public let macAddress: String?
    public let capabilities: [String]

    private enum CodingKeys: String, CodingKey {
        case name
        case macAddress  = "mac_address"
        case capabilities
    }

    public init(name: String, macAddress: String? = nil, capabilities: [String] = []) {
        self.name = name
        self.macAddress = macAddress
        self.capabilities = capabilities
    }
}
