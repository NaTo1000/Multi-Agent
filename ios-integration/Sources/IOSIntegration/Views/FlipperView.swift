import SwiftUI

/// Flipper Zero management view: BLE scan, file browser, and animation preview.
public struct FlipperView: View {
    @StateObject private var viewModel = FlipperViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            Group {
                if let device = viewModel.flipperDevice {
                    connectedView(device: device)
                } else {
                    scanView
                }
            }
            .navigationTitle("Flipper Zero")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if viewModel.flipperDevice != nil {
                        Button("Disconnect", role: .destructive) {
                            Task { await viewModel.disconnect() }
                        }
                    }
                }
            }
            .alert("Error", isPresented: $viewModel.showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }

    // MARK: - Scan view

    private var scanView: some View {
        VStack(spacing: 24) {
            Image(systemName: "flipphone")
                .font(.system(size: 64))
                .foregroundStyle(.secondary)

            Text("No Flipper Connected")
                .font(.title2.bold())

            Text("Tap Scan to discover Flipper Zero devices over Bluetooth LE.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 32)

            if viewModel.isScanning {
                ProgressView("Scanning…")
                Button("Stop") { viewModel.stopScan() }
                    .buttonStyle(.bordered)
            } else {
                Button("Scan for Flipper") {
                    Task { await viewModel.startScan() }
                }
                .buttonStyle(.borderedProminent)
            }

            if !viewModel.discoveredDevices.isEmpty {
                List(viewModel.discoveredDevices) { device in
                    Button(device.name) {
                        Task { await viewModel.connect(to: device) }
                    }
                }
                .frame(maxHeight: 200)
                .listStyle(.insetGrouped)
            }
        }
        .padding()
    }

    // MARK: - Connected view

    private func connectedView(device: FlipperDevice) -> some View {
        TabView {
            filesBrowserTab
                .tabItem { Label("Files", systemImage: "folder") }

            animationPreviewTab
                .tabItem { Label("Animations", systemImage: "film") }

            deviceInfoTab(device: device)
                .tabItem { Label("Info", systemImage: "info.circle") }
        }
    }

    private var filesBrowserTab: some View {
        Group {
            if viewModel.isLoadingFiles {
                ProgressView("Loading files…")
            } else {
                List(viewModel.files) { file in
                    HStack {
                        Image(systemName: file.isDirectory ? "folder.fill" : "doc.fill")
                            .foregroundStyle(file.isDirectory ? .yellow : .secondary)
                        VStack(alignment: .leading) {
                            Text(file.name)
                                .font(.subheadline)
                            if let size = file.size {
                                Text(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        if file.isDirectory {
                            Task { await viewModel.listFiles(at: file.path) }
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .overlay(alignment: .bottom) {
                    if viewModel.currentPath != "/" {
                        Button("← Back") {
                            viewModel.goUp()
                        }
                        .buttonStyle(.borderedProminent)
                        .padding()
                    }
                }
            }
        }
        .task {
            await viewModel.listFiles(at: "/")
        }
    }

    private var animationPreviewTab: some View {
        VStack {
            Text("Animation preview requires asset packs to be installed.")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding()
            NavigationLink("Open Asset Pack Browser") {
                AssetPackBrowserView()
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private func deviceInfoTab(device: FlipperDevice) -> some View {
        Form {
            Section("Device") {
                LabeledContent("Name", value: device.name)
                LabeledContent("Address", value: device.address)
                if let fw = device.firmwareVersion {
                    LabeledContent("Firmware", value: fw)
                }
            }
            Section("Storage") {
                if let free = device.sdCardFree {
                    LabeledContent("SD Free",
                        value: ByteCountFormatter.string(fromByteCount: Int64(free), countStyle: .file))
                }
            }
            Section("Battery") {
                if let bat = device.batteryLevel {
                    LabeledContent("Level", value: "\(bat)%")
                    ProgressView(value: Double(bat) / 100.0)
                }
            }
        }
    }
}

#Preview {
    FlipperView()
}
