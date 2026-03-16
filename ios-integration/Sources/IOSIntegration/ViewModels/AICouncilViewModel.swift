import Foundation

/// ViewModel driving the AI Council view.
///
/// Polls the AI council on demand or on a timed schedule, aggregating
/// recommendations from HuggingFace and WatsonX into published state.
@MainActor
public final class AICouncilViewModel: ObservableObject {

    // MARK: - Published state

    /// The most recent analysis produced by the council.
    @Published public var analysis: AICouncilAnalysis?

    /// Whether an analysis is currently in progress.
    @Published public var isAnalysing: Bool = false

    /// User-visible error message, set when analysis fails.
    @Published public var errorMessage: String?

    /// Whether the error alert should be visible.
    @Published public var showError: Bool = false

    // MARK: - Services

    private let council: AICouncilService
    private let orchestrator: OrchestratorService
    private let socket: TelemetrySocket

    /// Latest telemetry frames buffered for analysis.
    private var telemetryBuffer: [TelemetryData] = []
    private var telemetryTask: Task<Void, Never>?
    private var pollTask: Task<Void, Never>?

    // MARK: - Init

    public init(
        council: AICouncilService = AICouncilService(),
        orchestrator: OrchestratorService = OrchestratorService(),
        socket: TelemetrySocket = TelemetrySocket()
    ) {
        self.council = council
        self.orchestrator = orchestrator
        self.socket = socket
        startTelemetryBuffer()
    }

    deinit {
        telemetryTask?.cancel()
        pollTask?.cancel()
    }

    // MARK: - Public API

    /// Triggers an immediate on-demand analysis.
    public func runAnalysis() async {
        guard !isAnalysing else { return }
        isAnalysing = true
        defer { isAnalysing = false }

        do {
            let devices = try await orchestrator.fetchDevices()
            let snapshot = telemetryBuffer
            let result = try await council.analyse(telemetry: snapshot, devices: devices)
            analysis = result
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    /// Starts an automatic polling loop that analyses every `interval` seconds.
    public func startAutoPoll(interval: TimeInterval = 60) {
        stopAutoPoll()
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.runAnalysis()
                try? await Task.sleep(for: .seconds(interval))
            }
        }
    }

    /// Stops the automatic polling loop.
    public func stopAutoPoll() {
        pollTask?.cancel()
        pollTask = nil
    }

    // MARK: - Private

    /// Buffers incoming telemetry frames for analysis context.
    /// Capped at `maxBufferSize` to bound memory usage while retaining
    /// enough history for a meaningful AI analysis window.
    private let maxBufferSize = 100
    private func startTelemetryBuffer() {
        telemetryTask = Task { [weak self] in
            guard let self else { return }
            for await frame in await socket.telemetryStream() {
                self.telemetryBuffer.append(frame)
                if self.telemetryBuffer.count > self.maxBufferSize {
                    self.telemetryBuffer.removeFirst()
                }
            }
        }
    }
}
