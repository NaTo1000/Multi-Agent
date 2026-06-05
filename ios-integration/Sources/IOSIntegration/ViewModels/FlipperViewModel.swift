import Foundation

/// Drives the Flipper Zero management screen: BLE scan, connect, file browser.
@MainActor
public final class FlipperViewModel: ObservableObject {

    // MARK: - Published state

    @Published public var flipperDevice: FlipperDevice?
    @Published public var discoveredDevices: [FlipperDevice] = []
    @Published public var files: [FlipperFile] = []
    @Published public var currentPath: String = "/"
    @Published public var connectionState: BLEConnectionState = .disconnected
    @Published public var isScanning = false
    @Published public var isLoadingFiles = false
    @Published public var showError = false
    @Published public var errorMessage: String?

    public enum BLEConnectionState: Equatable {
        case disconnected
        case scanning
        case connecting
        case connected
        case failed(String)

        public static func == (lhs: BLEConnectionState, rhs: BLEConnectionState) -> Bool {
            switch (lhs, rhs) {
            case (.disconnected, .disconnected),
                 (.scanning, .scanning),
                 (.connecting, .connecting),
                 (.connected, .connected): return true
            case (.failed(let a), .failed(let b)): return a == b
            default: return false
            }
        }
    }

    // MARK: - Services

    private let bleManager: FlipperBLEManager
    private let fileManager: FlipperFileManager

    private var pathStack: [String] = []

    // MARK: - Init

    public init() {
        self.bleManager = FlipperBLEManager()
        self.fileManager = FlipperFileManager(bleManager: bleManager)
        observeBLEManager()
    }

    // MARK: - Public API

    public func startScan() async {
        isScanning = true
        connectionState = .scanning
        discoveredDevices = []
        await bleManager.startScan()
    }

    public func stopScan() {
        bleManager.stopScan()
        isScanning = false
        connectionState = .disconnected
    }

    public func connect(to device: FlipperDevice) async {
        stopScan()
        connectionState = .connecting
        do {
            try await bleManager.connect(to: device)
            flipperDevice = device
            connectionState = .connected
        } catch {
            connectionState = .failed(error.localizedDescription)
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func disconnect() async {
        await bleManager.disconnect()
        flipperDevice = nil
        files = []
        currentPath = "/"
        pathStack = []
        connectionState = .disconnected
    }

    public func listFiles(at path: String) async {
        isLoadingFiles = true
        defer { isLoadingFiles = false }
        do {
            if path != currentPath {
                pathStack.append(currentPath)
            }
            currentPath = path
            files = try await fileManager.listFiles(at: path)
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func goUp() {
        guard let prev = pathStack.popLast() else { return }
        Task { await listFiles(at: prev) }
    }

    // MARK: - Private

    private func observeBLEManager() {
        Task { [weak self] in
            guard let self else { return }
            for await discovered in bleManager.discoveredDeviceStream() {
                self.discoveredDevices.append(discovered)
            }
        }
    }
}
