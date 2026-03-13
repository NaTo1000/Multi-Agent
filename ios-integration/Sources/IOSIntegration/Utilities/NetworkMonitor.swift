import Foundation
import Network

/// Wraps `NWPathMonitor` and exposes network reachability as an `AsyncStream`.
public final class NetworkMonitor: @unchecked Sendable {

    public enum Status: Sendable, Equatable {
        case satisfied
        case unsatisfied
        case requiresConnection
    }

    public static let shared = NetworkMonitor()

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "com.multiagent.networkmonitor", qos: .utility)

    private var statusContinuations: [UUID: AsyncStream<Status>.Continuation] = [:]
    private let lock = NSLock()

    public private(set) var currentStatus: Status = .unsatisfied

    private init() {
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            let status: Status
            switch path.status {
            case .satisfied:          status = .satisfied
            case .unsatisfied:        status = .unsatisfied
            case .requiresConnection: status = .requiresConnection
            @unknown default:         status = .unsatisfied
            }
            self.currentStatus = status
            self.broadcast(status)
        }
        monitor.start(queue: queue)
    }

    deinit {
        monitor.cancel()
    }

    /// Returns an `AsyncStream` that yields `Status` values whenever connectivity changes.
    public func statusStream() -> AsyncStream<Status> {
        let id = UUID()
        return AsyncStream { [weak self] continuation in
            guard let self else { continuation.finish(); return }
            continuation.onTermination = { [weak self] _ in
                self?.remove(id: id)
            }
            // Immediately emit current status
            continuation.yield(self.currentStatus)
            self.add(continuation, id: id)
        }
    }

    public var isConnected: Bool { currentStatus == .satisfied }

    // MARK: - Private

    private func broadcast(_ status: Status) {
        lock.lock()
        let continuations = statusContinuations
        lock.unlock()
        for c in continuations.values { c.yield(status) }
    }

    private func add(_ continuation: AsyncStream<Status>.Continuation, id: UUID) {
        lock.lock()
        statusContinuations[id] = continuation
        lock.unlock()
    }

    private func remove(id: UUID) {
        lock.lock()
        statusContinuations.removeValue(forKey: id)
        lock.unlock()
    }
}
