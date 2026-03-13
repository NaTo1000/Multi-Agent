import SwiftUI

/// OTA firmware management: lists available builds and initiates flash operations.
public struct FirmwareView: View {
    @StateObject private var viewModel = FirmwareViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.releases.isEmpty {
                    ProgressView("Loading firmware builds…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if viewModel.releases.isEmpty {
                    ContentUnavailableView(
                        "No Builds Available",
                        systemImage: "arrow.down.circle",
                        description: Text("No firmware builds found on the backend.")
                    )
                } else {
                    List {
                        ForEach(viewModel.releases) { release in
                            FirmwareReleaseRow(
                                release: release,
                                progress: viewModel.flashProgress[release.id],
                                isFlashing: viewModel.flashingId == release.id
                            ) {
                                viewModel.selectedRelease = release
                                viewModel.showDevicePicker = true
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Firmware")
            .refreshable {
                await viewModel.fetchReleases()
            }
            .task {
                await viewModel.fetchReleases()
            }
            .alert("Error", isPresented: $viewModel.showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
            .sheet(isPresented: $viewModel.showDevicePicker) {
                DevicePickerSheet(viewModel: viewModel)
            }
        }
    }
}

// MARK: - Release row

private struct FirmwareReleaseRow: View {
    let release: FirmwareRelease
    let progress: Double?
    let isFlashing: Bool
    let onFlash: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("v\(release.version)")
                    .font(.headline)
                Spacer()
                Text(release.releaseDate.formatted(.dateTime.month().day().year()))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(release.changelog)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)

            if let size = release.fileSize {
                Text(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            if isFlashing, let p = progress {
                ProgressView("Flashing…", value: p)
                    .tint(.orange)
            } else if !isFlashing {
                Button("Flash to Devices…") { onFlash() }
                    .font(.caption.bold())
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Device picker sheet

private struct DevicePickerSheet: View {
    @ObservedObject var viewModel: FirmwareViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var selectedDevices: Set<String> = []

    var body: some View {
        NavigationStack {
            List(viewModel.availableDevices, selection: $selectedDevices) { device in
                Text(device.name)
            }
            .navigationTitle("Select Devices")
            .navigationBarTitleDisplayMode(.inline)
            .environment(\.editMode, .constant(.active))
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Flash \(selectedDevices.count)") {
                        Task {
                            await viewModel.flashSelected(deviceIds: Array(selectedDevices))
                            dismiss()
                        }
                    }
                    .disabled(selectedDevices.isEmpty)
                }
            }
        }
    }
}

// MARK: - ViewModel

@MainActor
private class FirmwareViewModel: ObservableObject {
    @Published var releases: [FirmwareRelease] = []
    @Published var availableDevices: [Device] = []
    @Published var flashProgress: [String: Double] = [:]
    @Published var flashingId: String? = nil
    @Published var isLoading = false
    @Published var showError = false
    @Published var errorMessage: String?
    @Published var showDevicePicker = false
    @Published var selectedRelease: FirmwareRelease?

    private let firmwareService = FirmwareService()
    private let orchestratorService = OrchestratorService()

    func fetchReleases() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let rel = firmwareService.listReleases()
            async let dev = orchestratorService.fetchDevices()
            releases = try await rel
            availableDevices = try await dev
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    func flashSelected(deviceIds: [String]) async {
        guard let release = selectedRelease else { return }
        flashingId = release.id
        flashProgress[release.id] = 0

        do {
            _ = try await firmwareService.download(release: release) { [weak self] p in
                Task { @MainActor [weak self] in
                    self?.flashProgress[release.id] = p * 0.8
                }
            }
            try await firmwareService.flash(release: release, deviceIds: deviceIds)
            flashProgress[release.id] = 1.0
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }

        flashingId = nil
    }
}

#Preview {
    FirmwareView()
}
