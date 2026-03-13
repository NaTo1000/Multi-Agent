import Foundation

/// Strongly-typed API endpoint constants for the Multi-Agent FastAPI backend.
/// All paths are relative to `AppConfig.shared.baseURL`.
public enum Endpoints {

    // MARK: - System

    /// `GET /api/v1/status` — overall system health check.
    public static let status = "/api/v1/status"

    // MARK: - Devices

    /// `GET /api/v1/devices` — list all registered ESP32 devices.
    public static let devices = "/api/v1/devices"

    /// `POST /api/v1/devices` — register a new device.
    public static let devicesCreate = "/api/v1/devices"

    /// `GET /api/v1/devices/{id}` — fetch a single device.
    public static func device(id: String) -> String { "/api/v1/devices/\(id)" }

    /// `PUT /api/v1/devices/{id}` — update device metadata.
    public static func deviceUpdate(id: String) -> String { "/api/v1/devices/\(id)" }

    /// `DELETE /api/v1/devices/{id}` — deregister a device.
    public static func deviceDelete(id: String) -> String { "/api/v1/devices/\(id)" }

    /// `GET /api/v1/devices/{id}/telemetry` — historical telemetry for a device.
    public static func deviceTelemetry(id: String) -> String { "/api/v1/devices/\(id)/telemetry" }

    // MARK: - Agents

    /// `GET /api/v1/agents` — list orchestrator agents.
    public static let agents = "/api/v1/agents"

    /// `GET /api/v1/agents/{id}` — get a specific agent.
    public static func agent(id: String) -> String { "/api/v1/agents/\(id)" }

    // MARK: - Tasks

    /// `GET /api/v1/tasks` — list queued / running tasks.
    public static let tasks = "/api/v1/tasks"

    /// `POST /api/v1/tasks` — dispatch a new task to an agent.
    public static let tasksCreate = "/api/v1/tasks"

    /// `GET /api/v1/tasks/{id}` — poll task status.
    public static func task(id: String) -> String { "/api/v1/tasks/\(id)" }

    /// `DELETE /api/v1/tasks/{id}` — cancel a pending task.
    public static func taskCancel(id: String) -> String { "/api/v1/tasks/\(id)" }

    // MARK: - Firmware

    /// `GET /api/v1/firmware/builds` — list available OTA firmware builds.
    public static let firmwareBuilds = "/api/v1/firmware/builds"

    /// `POST /api/v1/firmware/flash` — trigger OTA flash on one or more devices.
    public static let firmwareFlash = "/api/v1/firmware/flash"

    /// `GET /api/v1/firmware/builds/{version}` — fetch metadata for a specific build.
    public static func firmwareBuild(version: String) -> String { "/api/v1/firmware/builds/\(version)" }

    // MARK: - Asset Packs (Momentum / Flipper)

    /// `GET /api/v1/assets` — list cached asset packs on the backend.
    public static let assets = "/api/v1/assets"

    /// `POST /api/v1/assets/sync` — trigger backend sync with Momentum CDN.
    public static let assetsSync = "/api/v1/assets/sync"

    // MARK: - WebSocket

    /// WebSocket path for live telemetry streaming.
    public static let wsTelemetry = "/ws/telemetry"

    // MARK: - URL builder

    /// Constructs an absolute `URL` from a path constant using `AppConfig.shared.baseURL`.
    public static func url(for path: String, config: AppConfig = .shared) -> URL {
        config.baseURL.appendingPathComponent(path)
    }
}
