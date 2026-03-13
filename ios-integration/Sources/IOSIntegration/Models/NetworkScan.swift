import Foundation

/// A WiFi access point discovered during a Pineapple recon scan.
public struct NetworkScan: Codable, Identifiable, Sendable {
    public var id: String { bssid }
    public let ssid: String
    public let bssid: String
    /// 802.11 channel number (1–14 for 2.4 GHz, 36–177 for 5 GHz).
    public let channel: Int
    /// Signal strength in dBm.
    public let signal: Int
    public let encryption: EncryptionType
    /// MAC addresses of associated client stations.
    public let clients: [String]
    /// Timestamp when this AP was last seen.
    public let lastSeen: Date?

    public enum EncryptionType: String, Codable, Sendable {
        case open    = "OPEN"
        case wep     = "WEP"
        case wpa     = "WPA"
        case wpa2    = "WPA2"
        case wpa3    = "WPA3"
        case unknown = "UNKNOWN"
    }

    private enum CodingKeys: String, CodingKey {
        case ssid
        case bssid
        case channel
        case signal
        case encryption
        case clients
        case lastSeen = "last_seen"
    }

    public init(
        ssid: String,
        bssid: String,
        channel: Int,
        signal: Int,
        encryption: EncryptionType = .unknown,
        clients: [String] = [],
        lastSeen: Date? = nil
    ) {
        self.ssid = ssid
        self.bssid = bssid
        self.channel = channel
        self.signal = signal
        self.encryption = encryption
        self.clients = clients
        self.lastSeen = lastSeen
    }

    /// Human-readable signal quality label.
    public var signalLabel: String {
        switch signal {
        case -50...0:   return "Excellent"
        case -65 ... -51: return "Good"
        case -75 ... -66: return "Fair"
        default:        return "Poor"
        }
    }
}
