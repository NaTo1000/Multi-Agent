import Combine
import SwiftUI

/// Settings form for backend URLs, API token, and Pineapple configuration.
public struct SettingsView: View {
    @StateObject private var viewModel = SettingsViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            Form {
                backendSection
                webSocketSection
                pineappleSection
                authSection
                aboutSection
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        viewModel.save()
                    }
                    .disabled(!viewModel.isDirty)
                }
            }
            .onAppear {
                viewModel.load()
            }
            .alert("Saved", isPresented: $viewModel.didSave) {
                Button("OK", role: .cancel) {}
            }
        }
    }

    // MARK: - Sections

    private var backendSection: some View {
        Section {
            LabeledContent("Base URL") {
                TextField("http://localhost:8000", text: $viewModel.baseURL)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .multilineTextAlignment(.trailing)
            }
            LabeledContent("Timeout (s)") {
                TextField("30", text: $viewModel.requestTimeout)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
            }
        } header: {
            Text("FastAPI Backend")
        } footer: {
            Text("The REST API is served at \(viewModel.baseURL)/api/v1/")
        }
    }

    private var webSocketSection: some View {
        Section("WebSocket") {
            LabeledContent("WS URL") {
                TextField("ws://localhost:8000/ws/telemetry", text: $viewModel.wsURL)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .multilineTextAlignment(.trailing)
            }
        }
    }

    private var pineappleSection: some View {
        Section("WiFi Pineapple") {
            LabeledContent("Host") {
                TextField("172.16.42.1", text: $viewModel.pineappleHost)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .multilineTextAlignment(.trailing)
            }
            LabeledContent("API Key") {
                SecureField("Enter Pineapple API key", text: $viewModel.pineappleKey)
                    .multilineTextAlignment(.trailing)
            }
        }
    }

    private var authSection: some View {
        Section("Authentication") {
            LabeledContent("API Token") {
                SecureField("Bearer token", text: $viewModel.apiToken)
                    .multilineTextAlignment(.trailing)
            }
            Button("Clear Token", role: .destructive) {
                viewModel.clearToken()
            }
        }
    }

    private var aboutSection: some View {
        Section("About") {
            LabeledContent("Version", value: Bundle.main.appVersion)
            LabeledContent("Build", value: Bundle.main.appBuild)
            Link("GitHub Repository",
                 destination: URL(string: "https://github.com/your-org/Multi-Agent")!)
        }
    }
}

// MARK: - ViewModel

@MainActor
private class SettingsViewModel: ObservableObject {
    @Published var baseURL = ""
    @Published var wsURL = ""
    @Published var pineappleHost = ""
    @Published var pineappleKey = ""
    @Published var apiToken = ""
    @Published var requestTimeout = "30"
    @Published var didSave = false
    @Published var isDirty = false

    private let defaults = UserDefaults.standard

    func load() {
        baseURL        = defaults.string(forKey: "baseURL")       ?? AppConfig.shared.baseURL.absoluteString
        wsURL          = defaults.string(forKey: "wsURL")         ?? AppConfig.shared.webSocketURL.absoluteString
        pineappleHost  = defaults.string(forKey: "pineappleHost") ?? AppConfig.shared.pineappleHost
        requestTimeout = String(defaults.double(forKey: "requestTimeout") > 0
                         ? defaults.double(forKey: "requestTimeout")
                         : AppConfig.shared.requestTimeout)
        apiToken       = KeychainHelper.shared.read(key: KeychainHelper.apiTokenKey) ?? ""
        pineappleKey   = KeychainHelper.shared.read(key: KeychainHelper.pineappleKeyKey) ?? ""

        // Reset dirty flag after load
        objectWillChange.send()
        isDirty = false
        setupDirtyTracking()
    }

    func save() {
        defaults.set(baseURL, forKey: "baseURL")
        defaults.set(wsURL, forKey: "wsURL")
        defaults.set(pineappleHost, forKey: "pineappleHost")
        defaults.set(Double(requestTimeout) ?? 30, forKey: "requestTimeout")

        if !apiToken.isEmpty {
            KeychainHelper.shared.store(key: KeychainHelper.apiTokenKey, value: apiToken)
        }
        if !pineappleKey.isEmpty {
            KeychainHelper.shared.store(key: KeychainHelper.pineappleKeyKey, value: pineappleKey)
        }

        isDirty = false
        didSave = true
    }

    func clearToken() {
        KeychainHelper.shared.delete(key: KeychainHelper.apiTokenKey)
        apiToken = ""
    }

    private func setupDirtyTracking() {
        $baseURL.dropFirst().sink { [weak self] _ in self?.isDirty = true }.store(in: &cancellables)
        $wsURL.dropFirst().sink { [weak self] _ in self?.isDirty = true }.store(in: &cancellables)
        $pineappleHost.dropFirst().sink { [weak self] _ in self?.isDirty = true }.store(in: &cancellables)
        $apiToken.dropFirst().sink { [weak self] _ in self?.isDirty = true }.store(in: &cancellables)
        $requestTimeout.dropFirst().sink { [weak self] _ in self?.isDirty = true }.store(in: &cancellables)
    }

    private var cancellables = Set<AnyCancellable>()
}

// MARK: - Bundle helpers

private extension Bundle {
    var appVersion: String { infoDictionary?["CFBundleShortVersionString"] as? String ?? "—" }
    var appBuild:   String { infoDictionary?["CFBundleVersion"] as? String ?? "—" }
}

#Preview {
    SettingsView()
}
