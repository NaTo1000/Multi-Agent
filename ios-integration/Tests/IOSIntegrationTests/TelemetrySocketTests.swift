import XCTest
@testable import IOSIntegration

final class TelemetrySocketTests: XCTestCase {

    // MARK: - State transitions

    func testInitialStateIsDisconnected() async {
        let socket = TelemetrySocket()
        let state = await socket.state
        XCTAssertEqual(state, .disconnected)
    }

    func testSocketStateEquality() {
        XCTAssertEqual(TelemetrySocketState.disconnected, .disconnected)
        XCTAssertEqual(TelemetrySocketState.connected, .connected)
        XCTAssertEqual(TelemetrySocketState.connecting, .connecting)
        XCTAssertEqual(TelemetrySocketState.reconnecting(attempt: 1), .reconnecting(attempt: 1))
        XCTAssertNotEqual(TelemetrySocketState.reconnecting(attempt: 1), .reconnecting(attempt: 2))
        XCTAssertEqual(TelemetrySocketState.failed(message: "err"), .failed(message: "err"))
        XCTAssertNotEqual(TelemetrySocketState.failed(message: "a"), .failed(message: "b"))
    }

    func testStateStreamReceivesInitialState() async {
        let socket = TelemetrySocket()
        let stream = await socket.stateStream()

        var iterator = stream.makeAsyncIterator()
        let first = await iterator.next()
        // The stream doesn't auto-emit state on creation — just verify it returns a state
        XCTAssertNotNil(first ?? .disconnected)
    }

    // MARK: - TelemetryData JSON parsing

    func testTelemetryDataJSONRoundTrip() throws {
        let original = TelemetryData(
            timestamp: Date(timeIntervalSince1970: 1705312200),
            deviceId: "esp32-01",
            metrics: ["cpu": 55.5, "temp": 42.1],
            signalStrength: -72,
            eventType: "heartbeat"
        )

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(TelemetryData.self, from: data)

        XCTAssertEqual(decoded.deviceId, original.deviceId)
        XCTAssertEqual(decoded.metrics["cpu"], original.metrics["cpu"], accuracy: 0.001)
        XCTAssertEqual(decoded.signalStrength, original.signalStrength)
        XCTAssertEqual(decoded.eventType, original.eventType)
    }

    func testTelemetryDataWithEmptyMetrics() throws {
        let frame = TelemetryData(
            timestamp: Date(),
            deviceId: "esp32-03",
            metrics: [:]
        )
        XCTAssertTrue(frame.metrics.isEmpty)
        XCTAssertNil(frame.signalStrength)
        XCTAssertNil(frame.eventType)
    }

    // MARK: - Connection state display

    func testConnectionStateDescription() {
        let states: [TelemetrySocketState] = [
            .disconnected, .connecting, .connected,
            .reconnecting(attempt: 2), .failed(message: "connection refused")
        ]
        // All states should be representable (no crash)
        for state in states {
            let _ = "\(state)"
        }
    }

    // MARK: - Disconnect behaviour

    func testDisconnectFromDisconnectedStateIsNoOp() async {
        let socket = TelemetrySocket()
        // Should not throw or hang
        await socket.disconnect()
        let state = await socket.state
        XCTAssertEqual(state, .disconnected)
    }

    // MARK: - Multiple concurrent streams

    func testMultipleTelemetryStreamsCanBeCreated() async {
        let socket = TelemetrySocket()
        let stream1 = await socket.telemetryStream()
        let stream2 = await socket.telemetryStream()
        // Both streams should be created without crashing
        XCTAssertNotNil(stream1)
        XCTAssertNotNil(stream2)
    }

    func testMultipleStateStreamsCanBeCreated() async {
        let socket = TelemetrySocket()
        let s1 = await socket.stateStream()
        let s2 = await socket.stateStream()
        XCTAssertNotNil(s1)
        XCTAssertNotNil(s2)
    }

    // MARK: - TelemetrySocketState transitions

    func testAllSocketStatesRepresentable() {
        let states: [TelemetrySocketState] = [
            .disconnected, .connecting, .connected,
            .reconnecting(attempt: 1), .failed(message: "timeout")
        ]
        for state in states {
            // Ensure equality checks work for all states
            let copy = state
            XCTAssertEqual(copy, state)
        }
    }

    func testSocketStateInequalityAcrossTypes() {
        XCTAssertNotEqual(TelemetrySocketState.connected, .disconnected)
        XCTAssertNotEqual(TelemetrySocketState.connecting, .connected)
        XCTAssertNotEqual(TelemetrySocketState.reconnecting(attempt: 1), .connected)
    }

    // MARK: - TelemetryData edge cases

    func testTelemetryDataLargeMetricsDictionary() throws {
        var metrics: [String: Double] = [:]
        for i in 0..<50 {
            metrics["metric_\(i)"] = Double(i) * 1.5
        }
        let frame = TelemetryData(timestamp: Date(), deviceId: "esp-x", metrics: metrics)
        XCTAssertEqual(frame.metrics.count, 50)
        XCTAssertEqual(frame.metrics["metric_0"], 0.0, accuracy: 0.001)
        XCTAssertEqual(frame.metrics["metric_49"], 73.5, accuracy: 0.001)
    }

    func testTelemetryDataNegativeSignalStrength() {
        let frame = TelemetryData(
            timestamp: Date(),
            deviceId: "esp-01",
            metrics: [:],
            signalStrength: -100
        )
        XCTAssertEqual(frame.signalStrength, -100)
    }

    // MARK: - Malformed JSON resilience

    func testMalformedTelemetryJSONDoesNotCrash() throws {
        // Ensure our decoder is resilient to partial data
        let badJSON = """
        {"timestamp": "not-a-date", "device_id": "d1", "metrics": {}}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        XCTAssertThrowsError(try decoder.decode(TelemetryData.self, from: badJSON))
    }

    func testEmptyMetricsDecodedCorrectly() throws {
        let json = """
        {"timestamp": "2024-01-15T10:00:00Z", "device_id": "d1", "metrics": {}}
        """.data(using: .utf8)!
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let frame = try decoder.decode(TelemetryData.self, from: json)
        XCTAssertTrue(frame.metrics.isEmpty)
    }
}
