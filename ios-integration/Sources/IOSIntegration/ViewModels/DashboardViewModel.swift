import Foundation
import Combine

/// Dashboard ViewModel — drives the top-level fleet health overview.
@MainActor
public final class DashboardViewModel: ObservableObject {

    // MARK: - Published state

    @Published public var devices: [Device] = []
    @Published public var latestTelemetry: [TelemetryData] = []
    @Published public var connectionState: TelemetrySocketState = .disconnected
    @Published public var showError = false
    @Published public var errorMessage: String?

    // MARK: - Derived counters

    public var onlineCount: Int { devices.filter { $0.status == .online }.count }
    public var offlineCount: Int { devices.filter { $0.status == .offline }.count }
    public var busyCount:   Int { devices.filter { $0.status == .busy   }.count }

    // MARK: - Services

    private let orchestrator: OrchestratorService
    private let socket: TelemetrySocket

    private var socketTask:  Task<Void, Never>?
    private var stateTask:   Task<Void, Never>?

    // MARK: - Init

    public init(
        orchestrator: OrchestratorService = OrchestratorService(),
        socket: TelemetrySocket = TelemetrySocket()
    ) {
        self.orchestrator = orchestrator
        self.socket = socket
        startSocketListeners()
    }

    deinit {
        socketTask?.cancel()
        stateTask?.cancel()
    }

    // MARK: - Public API

    /// Fetches the latest device list and connects the telemetry socket.
    public func load() async {
        await fetchDevices()
        await socket.connect()
    }

    public func reconnectSocket() async {
        await socket.disconnect()
        try? await Task.sleep(for: .milliseconds(500))
        await socket.connect()
    }

    public func dispatchBroadcast() async {
        for device in devices where device.status == .online {
            let req = TaskRequest(agentId: device.id, action: "heartbeat")
            try? await orchestrator.dispatchTask(req)
        }
    }

    // MARK: - Private

    private func fetchDevices() async {
        do {
            devices = try await orchestrator.fetchDevices()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    private func startSocketListeners() {
        socketTask = Task { [weak self] in
            guard let self else { return }
            for await frame in await socket.telemetryStream() {
                self.latestTelemetry.append(frame)
                if self.latestTelemetry.count > 50 {
                    self.latestTelemetry.removeFirst()
                }
            }
        }

        stateTask = Task { [weak self] in
            guard let self else { return }
            for await state in await socket.stateStream() {
                self.connectionState = state
            }
        }
    }
}
