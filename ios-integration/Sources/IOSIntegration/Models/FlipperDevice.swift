import Foundation

/// Represents a Flipper Zero device discovered over BLE.
public struct FlipperDevice: Codable, Identifiable, Sendable {
    public let id: String          // BLE peripheral UUID string
    public var name: String
    /// BLE MAC address (or CBUUID string on iOS where MAC is hidden).
    public var address: String
    public var firmwareVersion: String?
    /// Battery level 0–100 percent.
    public var batteryLevel: Int?
    /// Free space on the SD card in bytes.
    public var sdCardFree: Int?
    public var isConnected: Bool

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case address
        case firmwareVersion = "firmware_version"
        case batteryLevel    = "battery_level"
        case sdCardFree      = "sd_card_free"
        case isConnected     = "is_connected"
    }

    public init(
        id: String,
        name: String,
        address: String,
        firmwareVersion: String? = nil,
        batteryLevel: Int? = nil,
        sdCardFree: Int? = nil,
        isConnected: Bool = false
    ) {
        self.id = id
        self.name = name
        self.address = address
        self.firmwareVersion = firmwareVersion
        self.batteryLevel = batteryLevel
        self.sdCardFree = sdCardFree
        self.isConnected = isConnected
    }
}

/// Represents a file or directory entry on the Flipper Zero SD card.
public struct FlipperFile: Codable, Identifiable, Sendable {
    public var id: String { path }
    public let path: String
    public let name: String
    public let isDirectory: Bool
    public let size: Int?

    private enum CodingKeys: String, CodingKey {
        case path
        case name
        case isDirectory = "is_directory"
        case size
    }

    public init(path: String, name: String, isDirectory: Bool, size: Int? = nil) {
        self.path = path
        self.name = name
        self.isDirectory = isDirectory
        self.size = size
    }
}
