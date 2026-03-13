import Foundation

/// A single telemetry frame emitted by an ESP32 device and delivered over
/// the WebSocket stream at `/ws/telemetry`.
public struct TelemetryData: Codable, Sendable {
    /// ISO-8601 timestamp of when the measurement was taken on-device.
    public let timestamp: Date
    /// ID of the originating device (matches `Device.id`).
    public let deviceId: String
    /// Named metric values — e.g. `["cpu": 42.5, "heap": 128000]`.
    public let metrics: [String: Double]
    /// RSSI in dBm, if available.
    public let signalStrength: Int?
    /// Optional event type tag (e.g. "boot", "alert", "heartbeat").
    public let eventType: String?

    private enum CodingKeys: String, CodingKey {
        case timestamp
        case deviceId       = "device_id"
        case metrics
        case signalStrength = "signal_strength"
        case eventType      = "event_type"
    }

    public init(
        timestamp: Date,
        deviceId: String,
        metrics: [String: Double],
        signalStrength: Int? = nil,
        eventType: String? = nil
    ) {
        self.timestamp = timestamp
        self.deviceId = deviceId
        self.metrics = metrics
        self.signalStrength = signalStrength
        self.eventType = eventType
    }
}
