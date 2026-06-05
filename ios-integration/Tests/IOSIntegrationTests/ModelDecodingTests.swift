import XCTest
@testable import IOSIntegration

final class ModelDecodingTests: XCTestCase {

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    // MARK: - Device

    func testDeviceDecoding() throws {
        let json = """
        {
            "id": "esp32-01",
            "name": "Node Alpha",
            "status": "online",
            "firmware_version": "1.2.3",
            "last_seen": "2024-01-15T10:30:00Z",
            "ip_address": "192.168.1.101",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "capabilities": ["wifi", "ble", "gpio"]
        }
        """.data(using: .utf8)!

        let device = try decoder.decode(Device.self, from: json)
        XCTAssertEqual(device.id, "esp32-01")
        XCTAssertEqual(device.name, "Node Alpha")
        XCTAssertEqual(device.status, .online)
        XCTAssertEqual(device.firmwareVersion, "1.2.3")
        XCTAssertEqual(device.ipAddress, "192.168.1.101")
        XCTAssertEqual(device.macAddress, "AA:BB:CC:DD:EE:FF")
        XCTAssertEqual(device.capabilities, ["wifi", "ble", "gpio"])
        XCTAssertNotNil(device.lastSeen)
    }

    func testDeviceStatusRawValues() {
        XCTAssertEqual(Device.DeviceStatus(rawValue: "online"),  .online)
        XCTAssertEqual(Device.DeviceStatus(rawValue: "offline"), .offline)
        XCTAssertEqual(Device.DeviceStatus(rawValue: "busy"),    .busy)
        XCTAssertEqual(Device.DeviceStatus(rawValue: "error"),   .error)
    }

    func testDeviceDecodingMinimal() throws {
        let json = """
        { "id": "x", "name": "Y", "status": "offline", "capabilities": [] }
        """.data(using: .utf8)!

        let device = try decoder.decode(Device.self, from: json)
        XCTAssertNil(device.firmwareVersion)
        XCTAssertNil(device.lastSeen)
        XCTAssertNil(device.ipAddress)
        XCTAssertNil(device.macAddress)
    }

    // MARK: - TelemetryData

    func testTelemetryDecoding() throws {
        let json = """
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "device_id": "esp32-01",
            "metrics": { "cpu": 42.5, "heap": 128000 },
            "signal_strength": -65,
            "event_type": "heartbeat"
        }
        """.data(using: .utf8)!

        let data = try decoder.decode(TelemetryData.self, from: json)
        XCTAssertEqual(data.deviceId, "esp32-01")
        XCTAssertEqual(data.metrics["cpu"], 42.5, accuracy: 0.001)
        XCTAssertEqual(data.metrics["heap"], 128000, accuracy: 0.001)
        XCTAssertEqual(data.signalStrength, -65)
        XCTAssertEqual(data.eventType, "heartbeat")
    }

    func testTelemetryDecodingOptionalFields() throws {
        let json = """
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "device_id": "esp32-02",
            "metrics": {}
        }
        """.data(using: .utf8)!

        let data = try decoder.decode(TelemetryData.self, from: json)
        XCTAssertNil(data.signalStrength)
        XCTAssertNil(data.eventType)
        XCTAssertTrue(data.metrics.isEmpty)
    }

    // MARK: - FirmwareRelease

    func testFirmwareReleaseDecoding() throws {
        let json = """
        {
            "id": "fw-001",
            "version": "2.0.0",
            "url": "https://example.com/firmware.bin",
            "sha256": "abcdef1234567890",
            "changelog": "Bug fixes and improvements",
            "release_date": "2024-01-15T00:00:00Z",
            "file_size": 1048576
        }
        """.data(using: .utf8)!

        let release = try decoder.decode(FirmwareRelease.self, from: json)
        XCTAssertEqual(release.id, "fw-001")
        XCTAssertEqual(release.version, "2.0.0")
        XCTAssertEqual(release.url.absoluteString, "https://example.com/firmware.bin")
        XCTAssertEqual(release.sha256, "abcdef1234567890")
        XCTAssertEqual(release.fileSize, 1048576)
    }

    // MARK: - NetworkScan

    func testNetworkScanDecoding() throws {
        let json = """
        {
            "ssid": "HomeNetwork",
            "bssid": "AA:BB:CC:DD:EE:FF",
            "channel": 6,
            "signal": -55,
            "encryption": "WPA2",
            "clients": ["11:22:33:44:55:66"],
            "last_seen": "2024-01-15T10:30:00Z"
        }
        """.data(using: .utf8)!

        let scan = try decoder.decode(NetworkScan.self, from: json)
        XCTAssertEqual(scan.ssid, "HomeNetwork")
        XCTAssertEqual(scan.bssid, "AA:BB:CC:DD:EE:FF")
        XCTAssertEqual(scan.channel, 6)
        XCTAssertEqual(scan.signal, -55)
        XCTAssertEqual(scan.encryption, .wpa2)
        XCTAssertEqual(scan.clients.count, 1)
    }

    func testNetworkScanSignalLabel() {
        let excellent = NetworkScan(ssid: "A", bssid: "00:00:00:00:00:01", channel: 1, signal: -40)
        XCTAssertEqual(excellent.signalLabel, "Excellent")

        let good = NetworkScan(ssid: "B", bssid: "00:00:00:00:00:02", channel: 1, signal: -60)
        XCTAssertEqual(good.signalLabel, "Good")

        let poor = NetworkScan(ssid: "C", bssid: "00:00:00:00:00:03", channel: 1, signal: -85)
        XCTAssertEqual(poor.signalLabel, "Poor")
    }

    // MARK: - AssetPack

    func testAssetPackDecoding() throws {
        let json = """
        {
            "id": "pack-001",
            "name": "Cool Pack",
            "author": "flipper_dev",
            "description": "A neat animation pack",
            "source_url": "https://cdn.example.com/packs/cool-pack",
            "previews": ["https://cdn.example.com/packs/cool-pack/preview.png"],
            "animations": [],
            "meta_version": 1
        }
        """.data(using: .utf8)!

        let pack = try decoder.decode(AssetPack.self, from: json)
        XCTAssertEqual(pack.id, "pack-001")
        XCTAssertEqual(pack.name, "Cool Pack")
        XCTAssertEqual(pack.author, "flipper_dev")
        XCTAssertEqual(pack.metaVersion, 1)
        XCTAssertEqual(pack.previews.count, 1)
    }

    // MARK: - Animation

    func testAnimationDecoding() throws {
        let json = """
        {
            "name": "Blinking",
            "width": 128,
            "height": 64,
            "frame_count": 10,
            "frame_rate": 5,
            "passive_frames": [0, 1, 2],
            "active_frames": [3, 4, 5, 6, 7, 8, 9]
        }
        """.data(using: .utf8)!

        let anim = try decoder.decode(Animation.self, from: json)
        XCTAssertEqual(anim.name, "Blinking")
        XCTAssertEqual(anim.width, 128)
        XCTAssertEqual(anim.height, 64)
        XCTAssertEqual(anim.frameCount, 10)
        XCTAssertEqual(anim.frameRate, 5)
        XCTAssertEqual(anim.duration, 2.0, accuracy: 0.001)
        XCTAssertEqual(anim.passiveFrames, [0, 1, 2])
        XCTAssertEqual(anim.activeFrames, [3, 4, 5, 6, 7, 8, 9])
    }

    // MARK: - FlipperDevice

    func testFlipperDeviceDecoding() throws {
        let json = """
        {
            "id": "ble-uuid-001",
            "name": "Flipper Alpha",
            "address": "AA:BB:CC:DD:EE:FF",
            "firmware_version": "0.93.1",
            "battery_level": 85,
            "sd_card_free": 2048000,
            "is_connected": true
        }
        """.data(using: .utf8)!

        let device = try decoder.decode(FlipperDevice.self, from: json)
        XCTAssertEqual(device.name, "Flipper Alpha")
        XCTAssertEqual(device.batteryLevel, 85)
        XCTAssertEqual(device.sdCardFree, 2048000)
        XCTAssertTrue(device.isConnected)
    }

    // MARK: - PineappleDevice

    func testPineappleDeviceDecoding() throws {
        let json = """
        {
            "id": "pine-01",
            "host": "172.16.42.1",
            "api_key": "testkey",
            "modules": ["PineAP", "Recon"],
            "recon_data": []
        }
        """.data(using: .utf8)!

        let device = try decoder.decode(PineappleDevice.self, from: json)
        XCTAssertEqual(device.host, "172.16.42.1")
        XCTAssertEqual(device.modules, ["PineAP", "Recon"])
        XCTAssertTrue(device.reconData.isEmpty)
    }

    func testPineappleDeviceMinimalDecoding() throws {
        let json = """
        {"id": "p1", "host": "10.0.0.1", "api_key": "", "modules": [], "recon_data": []}
        """.data(using: .utf8)!
        let device = try decoder.decode(PineappleDevice.self, from: json)
        XCTAssertEqual(device.host, "10.0.0.1")
        XCTAssertTrue(device.modules.isEmpty)
    }

    // MARK: - Device status helpers

    func testDeviceOnlineStatus() {
        let device = Device(id: "d1", name: "Test", status: .online, capabilities: [])
        XCTAssertTrue(device.status == .online)
    }

    func testDeviceCapabilities() {
        let device = Device(id: "d1", name: "Test", status: .online, capabilities: ["wifi", "ble", "gpio"])
        XCTAssertEqual(device.capabilities.count, 3)
        XCTAssertTrue(device.capabilities.contains("ble"))
    }

    // MARK: - TelemetryData init

    func testTelemetryDataInit() {
        let ts = Date()
        let frame = TelemetryData(timestamp: ts, deviceId: "d1", metrics: ["temp": 25.5])
        XCTAssertEqual(frame.deviceId, "d1")
        XCTAssertEqual(frame.metrics["temp"], 25.5, accuracy: 0.001)
        XCTAssertNil(frame.signalStrength)
    }

    // MARK: - NetworkScan EncryptionType raw values

    func testEncryptionTypeRawValues() {
        XCTAssertEqual(NetworkScan.EncryptionType(rawValue: "WPA2"), .wpa2)
        XCTAssertEqual(NetworkScan.EncryptionType(rawValue: "WPA3"), .wpa3)
        XCTAssertEqual(NetworkScan.EncryptionType(rawValue: "WEP"), .wep)
        XCTAssertEqual(NetworkScan.EncryptionType(rawValue: "Open"), .open)
        XCTAssertEqual(NetworkScan.EncryptionType(rawValue: "Unknown"), .unknown)
    }

    func testNetworkScanExcellentSignal() {
        let scan = NetworkScan(ssid: "X", bssid: "00:00:00:00:00:01", channel: 6, signal: -35)
        XCTAssertEqual(scan.signalLabel, "Excellent")
    }

    func testNetworkScanNoSignal() {
        let scan = NetworkScan(ssid: "X", bssid: "00:00:00:00:00:01", channel: 6, signal: -95)
        XCTAssertEqual(scan.signalLabel, "No Signal")
    }

    // MARK: - FirmwareRelease optional file size

    func testFirmwareReleaseOptionalFileSize() throws {
        let json = """
        {
            "id": "fw-002",
            "version": "3.0.0",
            "url": "https://example.com/fw.bin",
            "sha256": "abc123",
            "changelog": "New features",
            "release_date": "2024-06-01T00:00:00Z"
        }
        """.data(using: .utf8)!
        let release = try decoder.decode(FirmwareRelease.self, from: json)
        XCTAssertNil(release.fileSize)
    }

    // MARK: - AssetPack animations

    func testAssetPackWithAnimations() throws {
        let json = """
        {
            "id": "pack-002",
            "name": "Flipper Pack",
            "author": "dev",
            "description": "Cool animations",
            "source_url": "https://example.com",
            "previews": [],
            "meta_version": 2,
            "animations": [
                {
                    "name": "Wave",
                    "width": 128,
                    "height": 64,
                    "frame_count": 8,
                    "frame_rate": 4,
                    "passive_frames": [0,1,2,3],
                    "active_frames": [4,5,6,7]
                }
            ]
        }
        """.data(using: .utf8)!

        let pack = try decoder.decode(AssetPack.self, from: json)
        XCTAssertEqual(pack.animations.count, 1)
        XCTAssertEqual(pack.animations[0].name, "Wave")
        XCTAssertEqual(pack.animations[0].frameCount, 8)
        XCTAssertEqual(pack.animations[0].duration, 2.0, accuracy: 0.001)
    }

    // MARK: - JSON round-trip tests

    func testDeviceJSONRoundTrip() throws {
        let original = Device(
            id: "rt-01",
            name: "Round Trip",
            status: .busy,
            capabilities: ["wifi"]
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Device.self, from: data)
        XCTAssertEqual(decoded.id, original.id)
        XCTAssertEqual(decoded.status, original.status)
    }

    func testTelemetryDataJSONRoundTrip() throws {
        let original = TelemetryData(
            timestamp: Date(timeIntervalSince1970: 1_700_000_000),
            deviceId: "rt-02",
            metrics: ["cpu": 55.0, "temp": 38.2],
            signalStrength: -70,
            eventType: "sample"
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)
        let decoded = try decoder.decode(TelemetryData.self, from: data)
        XCTAssertEqual(decoded.deviceId, original.deviceId)
        XCTAssertEqual(decoded.metrics["cpu"], original.metrics["cpu"], accuracy: 0.001)
        XCTAssertEqual(decoded.signalStrength, original.signalStrength)
    }
}

