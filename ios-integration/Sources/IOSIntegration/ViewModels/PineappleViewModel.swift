import Foundation

/// Drives the WiFi Pineapple dashboard: connection, recon, modules, payloads.
@MainActor
public final class PineappleViewModel: ObservableObject {

    // MARK: - Published state

    @Published public var pineappleDevice: PineappleDevice?
    @Published public var modules: [PineappleModule] = []
    @Published public var reconData: [NetworkScan] = []
    @Published public var payloads: [DuckyPayload] = []
    @Published public var isConnected = false
    @Published public var isConnecting = false
    @Published public var isScanning = false
    @Published public var showError = false
    @Published public var errorMessage: String?

    public struct DuckyPayload: Identifiable {
        public let id = UUID()
        public let name: String
        public let description: String
        public let script: String
    }

    // MARK: - Services

    private let apiClient: PineappleAPIClient

    public init(apiClient: PineappleAPIClient = PineappleAPIClient()) {
        self.apiClient = apiClient
        loadBuiltinPayloads()
    }

    // MARK: - Connection

    public func connect() async {
        isConnecting = true
        defer { isConnecting = false }
        do {
            let device = PineappleDevice(
                host: AppConfig.shared.pineappleHost,
                apiKey: KeychainHelper.shared.read(key: KeychainHelper.pineappleKeyKey) ?? ""
            )
            // Verify connectivity by fetching modules
            let mods = try await apiClient.listModules()
            pineappleDevice = device
            modules = mods
            isConnected = true
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func disconnect() async {
        pineappleDevice = nil
        modules = []
        reconData = []
        isConnected = false
    }

    // MARK: - Recon

    public func startRecon() async {
        isScanning = true
        defer { isScanning = false }
        do {
            reconData = try await apiClient.getReconData()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    // MARK: - Modules

    public func fetchModules() async {
        do {
            modules = try await apiClient.listModules()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func enableModule(_ id: String) async {
        do {
            try await apiClient.enableModule(id)
            await fetchModules()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func disableModule(_ id: String) async {
        do {
            try await apiClient.disableModule(id)
            await fetchModules()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    // MARK: - Payloads

    public func runPayload(_ payload: DuckyPayload) async {
        do {
            try await apiClient.executePayload(script: payload.script)
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    private func loadBuiltinPayloads() {
        payloads = [
            DuckyPayload(
                name: "Info Gather",
                description: "Collects system info and exfiltrates via DNS",
                script: "DELAY 500\nGUI r\nDELAY 300\nSTRING cmd\nENTER"
            ),
            DuckyPayload(
                name: "Captive Portal",
                description: "Launches a captive portal to harvest credentials",
                script: "REM Captive portal payload"
            ),
            DuckyPayload(
                name: "Rickroll",
                description: "Opens YouTube in the browser",
                script: "DELAY 500\nGUI r\nDELAY 300\nSTRING https://youtu.be/dQw4w9WgXcQ\nENTER"
            ),
        ]
    }
}
