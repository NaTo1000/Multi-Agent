import Foundation

// MARK: - Combined telemetry

/// Aggregated telemetry from both the Flipper Zero and the WiFi Pineapple.
public struct CombinedTelemetry: Sendable {
    public let flipperNetworks: [NetworkScan]
    public let pineappleNetworks: [NetworkScan]
    public let mergedAt: Date

    /// Deduplicates by BSSID, preferring the Pineapple's scan when both sources see the same AP.
    public var merged: [NetworkScan] {
        var byBSSID: [String: NetworkScan] = [:]
        for scan in flipperNetworks { byBSSID[scan.bssid] = scan }
        for scan in pineappleNetworks { byBSSID[scan.bssid] = scan }
        return Array(byBSSID.values).sorted { $0.signal > $1.signal }
    }

    public init(flipper: [NetworkScan] = [], pineapple: [NetworkScan] = []) {
        self.flipperNetworks  = flipper
        self.pineappleNetworks = pineapple
        self.mergedAt = Date()
    }
}

// MARK: - Sync coordinator

/// Coordinates MAC address and scan data between a Flipper Zero and a WiFi Pineapple,
/// enabling combined intelligence from both devices.
public actor PineappleSync {

    private let apiClient: PineappleAPIClient

    public init(apiClient: PineappleAPIClient = PineappleAPIClient()) {
        self.apiClient = apiClient
    }

    // MARK: - Public API

    /// Uploads Flipper sub-GHz / WiFi scan results to the Pineapple recon endpoint,
    /// enriching the Pineapple's AP database with Flipper observations.
    public func syncMACAddresses(from flipperScans: [NetworkScan]) async throws {
        // Filter to valid BSSIDs (6-byte hex with colons)
        let validScans = flipperScans.filter { isValidBSSID($0.bssid) }
        guard !validScans.isEmpty else { return }

        // The Pineapple accepts recon data via its bulk-import endpoint
        let payload = SyncPayload(networks: validScans, source: "flipper")
        _ = try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            Task {
                do {
                    // In production this would POST to /api/v1/recon/import
                    // For now we trigger individual module interactions
                    for scan in validScans {
                        _ = try await apiClient.configurePineAP(
                            ssid: scan.ssid,
                            deauth: false,
                            harvesting: false
                        )
                    }
                    cont.resume()
                } catch {
                    cont.resume(throwing: error)
                }
            }
        }
    }

    /// Triggers a named Pineapple module (e.g. "recon", "pineap", "landingpage").
    public func triggerModule(_ module: String) async throws {
        try await apiClient.enableModule(module)
    }

    /// Returns telemetry from both the Flipper and the Pineapple in a unified structure.
    public func combinedTelemetry(flipperScans: [NetworkScan] = []) async -> CombinedTelemetry {
        let pineappleScans = (try? await apiClient.getReconData()) ?? []
        return CombinedTelemetry(flipper: flipperScans, pineapple: pineappleScans)
    }

    // MARK: - Private

    private func isValidBSSID(_ bssid: String) -> Bool {
        let parts = bssid.components(separatedBy: ":")
        guard parts.count == 6 else { return false }
        return parts.allSatisfy { part in
            part.count == 2 && part.allSatisfy { $0.isHexDigit }
        }
    }
}

// MARK: - Helpers

private struct SyncPayload: Encodable {
    let networks: [NetworkScan]
    let source: String
}
