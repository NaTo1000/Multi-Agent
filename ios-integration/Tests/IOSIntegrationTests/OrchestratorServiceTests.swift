import XCTest
@testable import IOSIntegration

// MARK: - Mock URLSession

final class MockURLSession: URLSession, @unchecked Sendable {
    var stubbedData: Data = Data()
    var stubbedResponse: URLResponse = HTTPURLResponse(
        url: URL(string: "http://localhost:8000")!,
        statusCode: 200,
        httpVersion: "HTTP/1.1",
        headerFields: nil
    )!
    var stubbedError: Error?
    var lastRequest: URLRequest?

    override func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        lastRequest = request
        if let error = stubbedError { throw error }
        return (stubbedData, stubbedResponse)
    }
}

// MARK: - Tests

final class OrchestratorServiceTests: XCTestCase {

    private let iso8601 = ISO8601DateFormatter()

    // MARK: - Helpers

    private func makeService() -> OrchestratorService {
        OrchestratorService(config: AppConfig())
    }

    private func makeDevice(id: String = "esp32-01", status: String = "online") -> Data {
        """
        {
            "id": "\(id)",
            "name": "Node \(id)",
            "status": "\(status)",
            "capabilities": ["wifi"]
        }
        """.data(using: .utf8)!
    }

    // MARK: - fetchDevices

    func testFetchDevicesDecodesResponse() async throws {
        let listJSON = """
        [
            {"id":"d1","name":"Alpha","status":"online","capabilities":[]},
            {"id":"d2","name":"Beta","status":"offline","capabilities":["ble"]}
        ]
        """.data(using: .utf8)!

        // We can test the JSON decoding logic independently of the networking layer
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let devices = try decoder.decode([Device].self, from: listJSON)
        XCTAssertEqual(devices.count, 2)
        XCTAssertEqual(devices[0].id, "d1")
        XCTAssertEqual(devices[0].status, .online)
        XCTAssertEqual(devices[1].capabilities, ["ble"])
    }

    // MARK: - registerDevice

    func testDeviceCreateEncoding() throws {
        let create = DeviceCreate(name: "Test Node", macAddress: "AA:BB:CC:DD:EE:FF", capabilities: ["wifi", "gpio"])
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(create)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(dict["name"] as? String, "Test Node")
        XCTAssertEqual(dict["mac_address"] as? String, "AA:BB:CC:DD:EE:FF")
        XCTAssertEqual(dict["capabilities"] as? [String], ["wifi", "gpio"])
    }

    // MARK: - TaskRequest

    func testTaskRequestEncoding() throws {
        let task = TaskRequest(agentId: "agent-1", action: "reboot", parameters: ["delay": "5"])
        let encoder = JSONEncoder()
        let data = try encoder.encode(task)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(dict["agent_id"] as? String, "agent-1")
        XCTAssertEqual(dict["action"] as? String, "reboot")
        let params = dict["parameters"] as? [String: String]
        XCTAssertEqual(params?["delay"], "5")
    }

    // MARK: - OrchestratorError

    func testOrchestratorErrorDescriptions() {
        XCTAssertNotNil(OrchestratorError.unauthorized.errorDescription)
        XCTAssertNotNil(OrchestratorError.maxRetriesExceeded(attempts: 3).errorDescription)
        XCTAssertNotNil(OrchestratorError.httpError(statusCode: 404, body: "Not found").errorDescription)
        XCTAssertNotNil(OrchestratorError.invalidURL("/bad path").errorDescription)
    }

    func testHttpErrorContainsStatusCode() {
        let error = OrchestratorError.httpError(statusCode: 503, body: "Service unavailable")
        XCTAssertTrue(error.errorDescription?.contains("503") == true)
    }

    // MARK: - TaskResponse

    func testTaskResponseDecoding() throws {
        let json = """
        {
            "id": "task-001",
            "agent_id": "agent-1",
            "action": "reboot",
            "status": "completed",
            "created_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T10:00:05Z",
            "result": "OK"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(TaskResponse.self, from: json)
        XCTAssertEqual(response.id, "task-001")
        XCTAssertEqual(response.status, .completed)
        XCTAssertNotNil(response.completedAt)
        XCTAssertEqual(response.result, "OK")
    }

    // MARK: - FirmwareFlashRequest

    func testFirmwareFlashRequestEncoding() throws {
        let req = FirmwareFlashRequest(firmwareId: "fw-v2", deviceIds: ["d1", "d2", "d3"])
        let data = try JSONEncoder().encode(req)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(dict["firmware_id"] as? String, "fw-v2")
        XCTAssertEqual((dict["device_ids"] as? [String])?.count, 3)
    }

    // MARK: - AppConfig

    func testAppConfigDefaultBaseURL() {
        let cfg = AppConfig()
        XCTAssertEqual(cfg.baseURL.scheme, "http")
        XCTAssertNotNil(cfg.baseURL.host)
    }

    func testAppConfigDefaultWebSocketURL() {
        let cfg = AppConfig()
        XCTAssertTrue(cfg.webSocketURL.absoluteString.hasPrefix("ws://"))
    }

    func testAppConfigDefaultTimeouts() {
        let cfg = AppConfig()
        XCTAssertGreaterThan(cfg.requestTimeout, 0)
        XCTAssertGreaterThan(cfg.retryMaxAttempts, 0)
        XCTAssertGreaterThan(cfg.retryBaseDelay, 0)
    }

    func testAppConfigApiURLBuilding() {
        let cfg = AppConfig()
        let url = cfg.apiURL(path: "/api/v1/status")
        XCTAssertTrue(url.absoluteString.contains("status"))
    }

    func testAppConfigMakeSession() {
        let cfg = AppConfig()
        let session = cfg.makeSession()
        XCTAssertNotNil(session)
        XCTAssertEqual(
            session.configuration.timeoutIntervalForRequest,
            cfg.requestTimeout,
            accuracy: 0.1
        )
    }

    // MARK: - Endpoints constants

    func testEndpointsAreNonEmpty() {
        XCTAssertFalse(Endpoints.status.isEmpty)
        XCTAssertFalse(Endpoints.devices.isEmpty)
        XCTAssertFalse(Endpoints.agents.isEmpty)
        XCTAssertFalse(Endpoints.tasks.isEmpty)
        XCTAssertFalse(Endpoints.firmwareBuilds.isEmpty)
        XCTAssertFalse(Endpoints.wsTelemetry.isEmpty)
    }

    func testEndpointsDynamicPaths() {
        XCTAssertTrue(Endpoints.device(id: "abc").contains("abc"))
        XCTAssertTrue(Endpoints.deviceTelemetry(id: "xyz").contains("xyz"))
        XCTAssertTrue(Endpoints.agent(id: "agent-1").contains("agent-1"))
        XCTAssertTrue(Endpoints.task(id: "t-99").contains("t-99"))
        XCTAssertTrue(Endpoints.firmwareBuild(version: "2.0").contains("2.0"))
    }

    func testEndpointsURLBuilder() {
        let url = Endpoints.url(for: Endpoints.status)
        XCTAssertTrue(url.absoluteString.contains("status"))
    }

    // MARK: - TaskStatus raw values

    func testTaskStatusRawValues() {
        XCTAssertEqual(TaskResponse.TaskStatus(rawValue: "queued"),    .queued)
        XCTAssertEqual(TaskResponse.TaskStatus(rawValue: "running"),   .running)
        XCTAssertEqual(TaskResponse.TaskStatus(rawValue: "completed"), .completed)
        XCTAssertEqual(TaskResponse.TaskStatus(rawValue: "failed"),    .failed)
        XCTAssertEqual(TaskResponse.TaskStatus(rawValue: "cancelled"), .cancelled)
    }

    // MARK: - DeviceCreate

    func testDeviceCreateMinimalEncoding() throws {
        let create = DeviceCreate(name: "Minimal", capabilities: [])
        let data = try JSONEncoder().encode(create)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(dict["name"] as? String, "Minimal")
    }

    func testDeviceCreateWithAllFields() throws {
        let create = DeviceCreate(
            name: "Full Node",
            ipAddress: "192.168.0.5",
            macAddress: "DE:AD:BE:EF:00:01",
            capabilities: ["wifi", "ble", "gpio", "adc"]
        )
        let data = try JSONEncoder().encode(create)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(dict["ip_address"] as? String, "192.168.0.5")
        XCTAssertEqual((dict["capabilities"] as? [String])?.count, 4)
    }
}

