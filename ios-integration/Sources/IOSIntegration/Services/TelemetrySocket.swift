import Foundation
import Starscream

// MARK: - Connection state

public enum TelemetrySocketState: Sendable, Equatable {
    case disconnected
    case connecting
    case connected
    case reconnecting(attempt: Int)
    case failed(message: String)

    public static func == (lhs: TelemetrySocketState, rhs: TelemetrySocketState) -> Bool {
        switch (lhs, rhs) {
        case (.disconnected, .disconnected),
             (.connecting, .connecting),
             (.connected, .connected):
            return true
        case (.reconnecting(let a), .reconnecting(let b)):
            return a == b
        case (.failed(let a), .failed(let b)):
            return a == b
        default:
            return false
        }
    }
}

// MARK: - Protocol

public protocol TelemetrySocketProtocol: Sendable {
    var state: TelemetrySocketState { get async }
    func connect() async
    func disconnect() async
    func telemetryStream() -> AsyncStream<TelemetryData>
    func stateStream() -> AsyncStream<TelemetrySocketState>
}

// MARK: - Actor implementation

/// Manages a persistent WebSocket connection to `/ws/telemetry`, delivering
/// live `TelemetryData` frames via `AsyncStream`.  Reconnects automatically
/// with exponential back-off when the connection drops.
public actor TelemetrySocket: TelemetrySocketProtocol {

    private let config: AppConfig
    private var socket: WebSocket?

    public private(set) var state: TelemetrySocketState = .disconnected

    // Continuations for broadcasting state changes and telemetry frames
    private var stateContinuations:     [UUID: AsyncStream<TelemetrySocketState>.Continuation] = [:]
    private var telemetryContinuations: [UUID: AsyncStream<TelemetryData>.Continuation] = [:]

    private var reconnectTask: Task<Void, Never>?
    private var reconnectAttempt = 0
    private let maxReconnectDelay: TimeInterval = 60

    private let decoder: JSONDecoder

    public init(config: AppConfig = .shared) {
        self.config = config
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
    }

    // MARK: - Public API

    public func connect() {
        guard state == .disconnected || state == .failed(message: "") else { return }
        openSocket()
    }

    public func disconnect() {
        reconnectTask?.cancel()
        reconnectTask = nil
        reconnectAttempt = 0
        socket?.disconnect()
        socket = nil
        updateState(.disconnected)
    }

    public func telemetryStream() -> AsyncStream<TelemetryData> {
        let id = UUID()
        return AsyncStream { [weak self] continuation in
            continuation.onTermination = { _ in
                Task { await self?.removeTelemetryContinuation(id: id) }
            }
            Task { await self?.addTelemetryContinuation(continuation, id: id) }
        }
    }

    public func stateStream() -> AsyncStream<TelemetrySocketState> {
        let id = UUID()
        return AsyncStream { [weak self] continuation in
            continuation.onTermination = { _ in
                Task { await self?.removeStateContinuation(id: id) }
            }
            Task { await self?.addStateContinuation(continuation, id: id) }
        }
    }

    // MARK: - Private

    private func openSocket() {
        var req = URLRequest(url: config.webSocketURL)
        if let token = KeychainHelper.shared.read(key: KeychainHelper.apiTokenKey) {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let ws = WebSocket(request: req)
        ws.onEvent = { [weak self] event in
            Task { await self?.handleEvent(event) }
        }
        self.socket = ws
        updateState(.connecting)
        ws.connect()
    }

    private func handleEvent(_ event: WebSocketEvent) {
        switch event {
        case .connected:
            reconnectAttempt = 0
            updateState(.connected)

        case .text(let string):
            if let data = string.data(using: .utf8) {
                parseTelemetry(data)
            }

        case .binary(let data):
            parseTelemetry(data)

        case .disconnected(let reason, _):
            AppLogger.telemetry.info("WebSocket disconnected: \(reason)")
            scheduleReconnect()

        case .error(let error):
            let msg = error?.localizedDescription ?? "unknown"
            AppLogger.telemetry.error("WebSocket error: \(msg)")
            updateState(.failed(message: msg))
            scheduleReconnect()

        case .cancelled:
            updateState(.disconnected)

        default:
            break
        }
    }

    private func parseTelemetry(_ data: Data) {
        do {
            let frame = try decoder.decode(TelemetryData.self, from: data)
            for continuation in telemetryContinuations.values {
                continuation.yield(frame)
            }
        } catch {
            AppLogger.telemetry.error("Failed to decode telemetry frame: \(error)")
        }
    }

    private func updateState(_ newState: TelemetrySocketState) {
        self.state = newState
        for continuation in stateContinuations.values {
            continuation.yield(newState)
        }
    }

    private func scheduleReconnect() {
        guard reconnectTask == nil || reconnectTask?.isCancelled == true else { return }
        reconnectAttempt += 1
        let attempt = reconnectAttempt
        updateState(.reconnecting(attempt: attempt))

        reconnectTask = Task { [weak self] in
            let base: TimeInterval = 1.0
            let delay = min(base * pow(2.0, Double(attempt - 1)), self?.maxReconnectDelay ?? 60)
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled else { return }
            await self?.openSocket()
        }
    }

    // Continuation management helpers
    private func addTelemetryContinuation(_ c: AsyncStream<TelemetryData>.Continuation, id: UUID) {
        telemetryContinuations[id] = c
    }
    private func removeTelemetryContinuation(id: UUID) {
        telemetryContinuations.removeValue(forKey: id)
    }
    private func addStateContinuation(_ c: AsyncStream<TelemetrySocketState>.Continuation, id: UUID) {
        stateContinuations[id] = c
    }
    private func removeStateContinuation(id: UUID) {
        stateContinuations.removeValue(forKey: id)
    }
}
