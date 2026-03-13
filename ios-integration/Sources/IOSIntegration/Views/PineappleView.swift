import SwiftUI

/// WiFi Pineapple dashboard with Recon, Modules, and Payloads tabs.
public struct PineappleView: View {
    @StateObject private var viewModel = PineappleViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            if viewModel.isConnected {
                TabView {
                    reconTab
                        .tabItem { Label("Recon", systemImage: "antenna.radiowaves.left.and.right") }

                    modulesTab
                        .tabItem { Label("Modules", systemImage: "puzzlepiece.fill") }

                    payloadsTab
                        .tabItem { Label("Payloads", systemImage: "terminal.fill") }
                }
                .navigationTitle("WiFi Pineapple")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Disconnect", role: .destructive) {
                            Task { await viewModel.disconnect() }
                        }
                    }
                }
            } else {
                connectView
                    .navigationTitle("WiFi Pineapple")
            }
        }
        .alert("Error", isPresented: $viewModel.showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }

    // MARK: - Connect

    private var connectView: some View {
        VStack(spacing: 20) {
            Image(systemName: "wifi.router")
                .font(.system(size: 64))
                .foregroundStyle(.orange)

            Text("Connect to Pineapple")
                .font(.title2.bold())

            Text("Host: \(AppConfig.shared.pineappleHost)")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if viewModel.isConnecting {
                ProgressView("Connecting…")
            } else {
                Button("Connect") {
                    Task { await viewModel.connect() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
    }

    // MARK: - Recon tab

    private var reconTab: some View {
        List {
            Section {
                Button("Start Scan") {
                    Task { await viewModel.startRecon() }
                }
                .frame(maxWidth: .infinity)
                .disabled(viewModel.isScanning)
            }

            Section("Access Points (\(viewModel.reconData.count))") {
                if viewModel.isScanning {
                    HStack {
                        ProgressView()
                        Text("Scanning…")
                    }
                } else {
                    ForEach(viewModel.reconData) { ap in
                        ReconRow(scan: ap)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .refreshable {
            await viewModel.startRecon()
        }
    }

    // MARK: - Modules tab

    private var modulesTab: some View {
        List(viewModel.modules) { module in
            HStack {
                VStack(alignment: .leading) {
                    Text(module.name).font(.headline)
                    if let desc = module.description {
                        Text(desc).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Spacer()
                Toggle("", isOn: Binding(
                    get: { module.isEnabled },
                    set: { enabled in
                        Task {
                            if enabled {
                                await viewModel.enableModule(module.id)
                            } else {
                                await viewModel.disableModule(module.id)
                            }
                        }
                    }
                ))
                .labelsHidden()
            }
        }
        .listStyle(.insetGrouped)
        .refreshable {
            await viewModel.fetchModules()
        }
        .task {
            await viewModel.fetchModules()
        }
    }

    // MARK: - Payloads tab

    private var payloadsTab: some View {
        VStack(spacing: 16) {
            Text("DuckyScript Payloads")
                .font(.headline)

            ForEach(viewModel.payloads, id: \.name) { payload in
                HStack {
                    VStack(alignment: .leading) {
                        Text(payload.name).font(.subheadline.bold())
                        Text(payload.description).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Run") {
                        Task { await viewModel.runPayload(payload) }
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                }
                .padding()
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 10))
            }

            Spacer()
        }
        .padding()
    }
}

// MARK: - Recon row

private struct ReconRow: View {
    let scan: NetworkScan

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(scan.ssid.isEmpty ? "(hidden)" : scan.ssid)
                    .font(.headline)
                Spacer()
                Text(scan.encryption.rawValue)
                    .font(.caption)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(encryptionColor(scan.encryption).opacity(0.2),
                                in: Capsule())
                    .foregroundStyle(encryptionColor(scan.encryption))
            }
            HStack {
                Text(scan.bssid).font(.caption2.monospaced()).foregroundStyle(.secondary)
                Spacer()
                Text("ch \(scan.channel)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text("\(scan.signal) dBm")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            if !scan.clients.isEmpty {
                Text("\(scan.clients.count) client(s)")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }
        }
        .padding(.vertical, 2)
    }

    private func encryptionColor(_ enc: NetworkScan.EncryptionType) -> Color {
        switch enc {
        case .open:    return .red
        case .wep:     return .orange
        case .wpa:     return .yellow
        case .wpa2, .wpa3: return .green
        case .unknown: return .gray
        }
    }
}

#Preview {
    PineappleView()
}
