import Foundation

// MARK: - Recon result

/// A structured summary of a complete recon scan session.
public struct ReconSession: Codable, Sendable {
    public let id: UUID
    public let startedAt: Date
    public let completedAt: Date?
    public let accessPoints: [NetworkScan]
    public let clientAssociations: [String: [String]]  // AP BSSID → [client MACs]

    public init(
        id: UUID = UUID(),
        startedAt: Date = Date(),
        completedAt: Date? = nil,
        accessPoints: [NetworkScan] = [],
        clientAssociations: [String: [String]] = [:]
    ) {
        self.id = id
        self.startedAt = startedAt
        self.completedAt = completedAt
        self.accessPoints = accessPoints
        self.clientAssociations = clientAssociations
    }

    // MARK: - Derived helpers

    /// Returns the AP with the strongest signal.
    public var strongestAP: NetworkScan? {
        accessPoints.max(by: { $0.signal < $1.signal })
    }

    /// Returns APs on a specific 802.11 channel.
    public func accessPoints(onChannel channel: Int) -> [NetworkScan] {
        accessPoints.filter { $0.channel == channel }
    }

    /// Returns all unique client MAC addresses seen across all APs.
    public var allClients: [String] {
        Array(Set(accessPoints.flatMap { $0.clients })).sorted()
    }

    /// Returns APs using open (unencrypted) authentication.
    public var openNetworks: [NetworkScan] {
        accessPoints.filter { $0.encryption.uppercased() == "OPEN" }
    }

    // MARK: - Export

    /// Serialises the session to a JSON `Data` blob.
    public func toJSON() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(self)
    }

    /// Converts the session to a CSV string with columns:
    /// SSID, BSSID, Channel, Signal (dBm), Encryption, Client Count
    public func toCSV() -> String {
        var lines = ["SSID,BSSID,Channel,Signal (dBm),Encryption,Clients"]
        for ap in accessPoints {
            let ssid = ap.ssid.isEmpty ? "(hidden)" : ap.ssid
            let row = [
                "\"\(ssid)\"",
                ap.bssid,
                "\(ap.channel)",
                "\(ap.signal)",
                ap.encryption,
                "\(ap.clients.count)"
            ].joined(separator: ",")
            lines.append(row)
        }
        return lines.joined(separator: "\n")
    }
}

// MARK: - Channel utilisation

/// Analyses channel utilisation across detected APs to suggest the least congested channel.
public struct ChannelAnalyser {

    /// Returns a dictionary mapping channel number → count of APs on that channel.
    public static func channelUsage(from scans: [NetworkScan]) -> [Int: Int] {
        var usage: [Int: Int] = [:]
        for scan in scans {
            usage[scan.channel, default: 0] += 1
        }
        return usage
    }

    /// Suggests the least used 2.4 GHz channel (1, 6, or 11).
    public static func suggestedChannel24GHz(from scans: [NetworkScan]) -> Int {
        let usage = channelUsage(from: scans)
        let candidates = [1, 6, 11]
        return candidates.min(by: { usage[$0, default: 0] < usage[$1, default: 0] }) ?? 1
    }
}
