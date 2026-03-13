import Foundation

/// Metadata for a firmware build available for OTA distribution to ESP32 devices.
public struct FirmwareRelease: Codable, Identifiable, Sendable {
    public let id: String
    public let version: String
    /// Download URL for the binary / DFU file.
    public let url: URL
    /// Hex-encoded SHA-256 checksum of the firmware file.
    public let sha256: String
    public let changelog: String
    public let releaseDate: Date
    /// File size in bytes (optional — may be absent for older entries).
    public let fileSize: Int?

    private enum CodingKeys: String, CodingKey {
        case id
        case version
        case url
        case sha256
        case changelog
        case releaseDate = "release_date"
        case fileSize    = "file_size"
    }

    public init(
        id: String,
        version: String,
        url: URL,
        sha256: String,
        changelog: String,
        releaseDate: Date,
        fileSize: Int? = nil
    ) {
        self.id = id
        self.version = version
        self.url = url
        self.sha256 = sha256
        self.changelog = changelog
        self.releaseDate = releaseDate
        self.fileSize = fileSize
    }
}

/// A request to trigger an OTA flash on one or more devices.
public struct FirmwareFlashRequest: Codable, Sendable {
    public let firmwareId: String
    public let deviceIds: [String]

    private enum CodingKeys: String, CodingKey {
        case firmwareId = "firmware_id"
        case deviceIds  = "device_ids"
    }

    public init(firmwareId: String, deviceIds: [String]) {
        self.firmwareId = firmwareId
        self.deviceIds = deviceIds
    }
}

/// Tracks the progress of an ongoing firmware flash operation.
public struct FirmwareFlashProgress: Sendable {
    public let deviceId: String
    public let bytesWritten: Int
    public let totalBytes: Int
    public var fraction: Double { totalBytes > 0 ? Double(bytesWritten) / Double(totalBytes) : 0 }
}
