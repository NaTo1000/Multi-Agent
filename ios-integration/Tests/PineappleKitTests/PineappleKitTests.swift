import XCTest
@testable import PineappleKit

final class PineappleKitTests: XCTestCase {

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    // MARK: - NetworkScan

    func testNetworkScanDecoding() throws {
        let json = """
        [
            {"ssid":"OpenCafe","bssid":"AA:BB:CC:DD:EE:01","channel":1,"signal":-45,
             "encryption":"OPEN","clients":[]},
            {"ssid":"SecureHome","bssid":"AA:BB:CC:DD:EE:02","channel":11,"signal":-65,
             "encryption":"WPA2","clients":["11:22:33:44:55:66","AA:BB:CC:00:11:22"]}
        ]
        """.data(using: .utf8)!

        let scans = try decoder.decode([NetworkScan].self, from: json)
        XCTAssertEqual(scans.count, 2)
        XCTAssertEqual(scans[0].ssid, "OpenCafe")
        XCTAssertEqual(scans[0].encryption, "OPEN")
        XCTAssertTrue(scans[0].clients.isEmpty)
        XCTAssertEqual(scans[1].clients.count, 2)
    }

    func testNetworkScanIdentifiableByBSSID() {
        let scan = NetworkScan(ssid: "Test", bssid: "AA:BB:CC:DD:EE:FF", channel: 6, signal: -60)
        XCTAssertEqual(scan.id, "AA:BB:CC:DD:EE:FF")
    }

    // MARK: - PineappleModule

    func testPineappleModuleDecoding() throws {
        let json = """
        [
            {"id":"recon","name":"Recon","is_enabled":true,"version":"2.1.0",
             "description":"Network reconnaissance"},
            {"id":"pineap","name":"PineAP","is_enabled":false,"version":null,"description":null}
        ]
        """.data(using: .utf8)!

        let modules = try decoder.decode([PineappleModule].self, from: json)
        XCTAssertEqual(modules.count, 2)
        XCTAssertTrue(modules[0].isEnabled)
        XCTAssertFalse(modules[1].isEnabled)
        XCTAssertNil(modules[1].version)
    }

    // MARK: - ReconSession

    func testReconSessionStrongestAP() {
        let scans = [
            NetworkScan(ssid: "A", bssid: "00:00:00:00:00:01", channel: 1, signal: -80),
            NetworkScan(ssid: "B", bssid: "00:00:00:00:00:02", channel: 6, signal: -45),
            NetworkScan(ssid: "C", bssid: "00:00:00:00:00:03", channel: 11, signal: -65),
        ]
        let session = ReconSession(accessPoints: scans)
        XCTAssertEqual(session.strongestAP?.ssid, "B")
    }

    func testReconSessionOpenNetworks() {
        let scans = [
            NetworkScan(ssid: "Open1", bssid: "00:00:00:00:00:01", channel: 1, signal: -50, encryption: "OPEN"),
            NetworkScan(ssid: "Secure", bssid: "00:00:00:00:00:02", channel: 6, signal: -55, encryption: "WPA2"),
            NetworkScan(ssid: "Open2", bssid: "00:00:00:00:00:03", channel: 11, signal: -60, encryption: "OPEN"),
        ]
        let session = ReconSession(accessPoints: scans)
        XCTAssertEqual(session.openNetworks.count, 2)
    }

    func testReconSessionAllClients() {
        let scans = [
            NetworkScan(ssid: "A", bssid: "00:00:00:00:00:01", channel: 1, signal: -50,
                        clients: ["11:11:11:11:11:11", "22:22:22:22:22:22"]),
            NetworkScan(ssid: "B", bssid: "00:00:00:00:00:02", channel: 6, signal: -55,
                        clients: ["33:33:33:33:33:33"]),
        ]
        let session = ReconSession(accessPoints: scans)
        XCTAssertEqual(session.allClients.count, 3)
    }

    func testReconSessionCSVExport() {
        let scans = [
            NetworkScan(ssid: "MyWiFi", bssid: "AA:BB:CC:DD:EE:FF", channel: 6, signal: -55, encryption: "WPA2"),
        ]
        let session = ReconSession(accessPoints: scans)
        let csv = session.toCSV()
        XCTAssertTrue(csv.contains("SSID"))
        XCTAssertTrue(csv.contains("MyWiFi"))
        XCTAssertTrue(csv.contains("AA:BB:CC:DD:EE:FF"))
        XCTAssertTrue(csv.contains("WPA2"))
    }

    func testReconSessionJSONExport() throws {
        let scans = [
            NetworkScan(ssid: "Test", bssid: "00:00:00:00:00:01", channel: 1, signal: -60),
        ]
        let session = ReconSession(accessPoints: scans)
        let json = try session.toJSON()
        XCTAssertFalse(json.isEmpty)

        let dict = try JSONSerialization.jsonObject(with: json) as? [String: Any]
        XCTAssertNotNil(dict?["accessPoints"] ?? dict?["access_points"])
    }

    // MARK: - ChannelAnalyser

    func testChannelUsageCount() {
        let scans = [
            NetworkScan(ssid: "A", bssid: "00:00:00:00:00:01", channel: 1, signal: -50),
            NetworkScan(ssid: "B", bssid: "00:00:00:00:00:02", channel: 1, signal: -55),
            NetworkScan(ssid: "C", bssid: "00:00:00:00:00:03", channel: 6, signal: -60),
        ]
        let usage = ChannelAnalyser.channelUsage(from: scans)
        XCTAssertEqual(usage[1], 2)
        XCTAssertEqual(usage[6], 1)
    }

    func testSuggestedChannel() {
        // Channel 11 is empty, should be suggested
        let scans = [
            NetworkScan(ssid: "A", bssid: "00:00:00:00:00:01", channel: 1, signal: -50),
            NetworkScan(ssid: "B", bssid: "00:00:00:00:00:02", channel: 1, signal: -55),
            NetworkScan(ssid: "C", bssid: "00:00:00:00:00:03", channel: 6, signal: -60),
        ]
        let suggested = ChannelAnalyser.suggestedChannel24GHz(from: scans)
        XCTAssertEqual(suggested, 11)
    }

    // MARK: - DuckyPayload validation

    func testDuckyPayloadValidSimple() {
        let payload = DuckyPayload(
            name: "Test",
            description: "Simple test",
            script: "REM This is a comment\nDELAY 500\nGUI r"
        )
        XCTAssertTrue(payload.isValid)
    }

    func testDuckyPayloadInvalidCommand() {
        let payload = DuckyPayload(
            name: "Bad",
            description: "Invalid script",
            script: "REM OK\nINVALID_COMMAND\nENTER"
        )
        XCTAssertFalse(payload.isValid)
    }

    // MARK: - CombinedTelemetry

    func testCombinedTelemetryMerging() {
        let flipperScans = [
            NetworkScan(ssid: "FlipperNet", bssid: "AA:00:00:00:00:01", channel: 1, signal: -70),
        ]
        let pineappleScans = [
            NetworkScan(ssid: "FlipperNet", bssid: "AA:00:00:00:00:01", channel: 1, signal: -55), // same BSSID, better signal
            NetworkScan(ssid: "PineappleNet", bssid: "BB:00:00:00:00:01", channel: 6, signal: -50),
        ]
        let combined = CombinedTelemetry(flipper: flipperScans, pineapple: pineappleScans)
        // Merged should have 2 unique BSSIDs (Pineapple wins for duplicate)
        XCTAssertEqual(combined.merged.count, 2)
        let flipperNet = combined.merged.first { $0.bssid == "AA:00:00:00:00:01" }
        XCTAssertEqual(flipperNet?.signal, -55)  // Pineapple's reading wins
    }

    // MARK: - PineappleError descriptions

    func testPineappleErrorDescriptions() {
        XCTAssertNotNil(PineappleError.invalidHost("bad-host").errorDescription)
        XCTAssertNotNil(PineappleError.missingAPIKey.errorDescription)
        XCTAssertNotNil(PineappleError.unauthorized.errorDescription)
        XCTAssertNotNil(PineappleError.httpError(statusCode: 500, body: "error").errorDescription)
    }
}
