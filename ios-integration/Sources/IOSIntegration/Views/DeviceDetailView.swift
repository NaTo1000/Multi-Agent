import SwiftUI
import Charts

/// Detailed view for a single ESP32 device with real-time telemetry charts.
public struct DeviceDetailView: View {
    let device: Device
    @StateObject private var viewModel: DeviceDetailViewModel

    public init(device: Device) {
        self.device = device
        _viewModel = StateObject(wrappedValue: DeviceDetailViewModel(device: device))
    }

    public var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                deviceHeaderCard
                telemetryChartsSection
                capabilitiesSection
            }
            .padding()
        }
        .navigationTitle(device.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button("Flash Firmware", systemImage: "arrow.down.circle") {
                        viewModel.showFirmwareSheet = true
                    }
                    Button("Dispatch Task", systemImage: "paperplane") {
                        viewModel.showTaskSheet = true
                    }
                    Divider()
                    Button("Remove Device", systemImage: "trash", role: .destructive) {
                        viewModel.showDeleteConfirm = true
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .task {
            await viewModel.startTelemetry()
        }
        .onDisappear {
            viewModel.stopTelemetry()
        }
        .confirmationDialog("Delete \(device.name)?", isPresented: $viewModel.showDeleteConfirm, titleVisibility: .visible) {
            Button("Delete", role: .destructive) { Task { await viewModel.deleteDevice() } }
            Button("Cancel", role: .cancel) {}
        }
        .sheet(isPresented: $viewModel.showFirmwareSheet) {
            FirmwareView()
        }
    }

    // MARK: - Subviews

    private var deviceHeaderCard: some View {
        VStack(spacing: 10) {
            HStack {
                Label(device.status.rawValue.capitalized, systemImage: "circle.fill")
                    .foregroundStyle(device.status.color)
                    .font(.headline)
                Spacer()
                if let fw = device.firmwareVersion {
                    Text("v\(fw)")
                        .font(.caption)
                        .padding(4)
                        .background(.quaternary, in: Capsule())
                }
            }

            Divider()

            VStack(alignment: .leading, spacing: 6) {
                if let ip = device.ipAddress {
                    LabeledContent("IP", value: ip)
                }
                if let mac = device.macAddress {
                    LabeledContent("MAC", value: mac)
                }
                if let last = device.lastSeen {
                    LabeledContent("Last seen", value: last.formatted(.relative(presentation: .named)))
                }
            }
            .font(.subheadline)
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var telemetryChartsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Live Telemetry", systemImage: "waveform.path.ecg")
                .font(.headline)

            if viewModel.telemetryHistory.isEmpty {
                Text("Waiting for data…")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 80)
            } else {
                TelemetryGraphView(
                    data: viewModel.telemetryHistory,
                    metric: viewModel.selectedMetric
                )
                .frame(height: 200)

                // Metric picker
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(viewModel.availableMetrics, id: \.self) { metric in
                            Button(metric) {
                                viewModel.selectedMetric = metric
                            }
                            .buttonStyle(.bordered)
                            .tint(viewModel.selectedMetric == metric ? .accentColor : .secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var capabilitiesSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Capabilities", systemImage: "puzzlepiece.extension.fill")
                .font(.headline)

            FlowLayout(data: device.capabilities) { cap in
                Text(cap)
                    .font(.caption)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Color.accentColor.opacity(0.15), in: Capsule())
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Detail ViewModel (local, lightweight)

@MainActor
private class DeviceDetailViewModel: ObservableObject {
    let device: Device
    @Published var telemetryHistory: [TelemetryData] = []
    @Published var selectedMetric: String = "cpu"
    @Published var showFirmwareSheet = false
    @Published var showTaskSheet = false
    @Published var showDeleteConfirm = false

    private let socket = TelemetrySocket()
    private var streamTask: Task<Void, Never>?

    var availableMetrics: [String] {
        Array(Set(telemetryHistory.flatMap { $0.metrics.keys })).sorted()
    }

    init(device: Device) {
        self.device = device
    }

    func startTelemetry() async {
        await socket.connect()
        streamTask = Task { [weak self] in
            guard let self else { return }
            for await frame in await socket.telemetryStream() {
                guard frame.deviceId == device.id else { continue }
                self.telemetryHistory.append(frame)
                if self.telemetryHistory.count > 200 {
                    self.telemetryHistory.removeFirst()
                }
                if self.selectedMetric.isEmpty,
                   let first = frame.metrics.keys.sorted().first {
                    self.selectedMetric = first
                }
            }
        }
    }

    func stopTelemetry() {
        streamTask?.cancel()
        streamTask = nil
        Task { await socket.disconnect() }
    }

    func deleteDevice() async {
        let service = OrchestratorService()
        try? await service.deleteDevice(id: device.id)
    }
}

// MARK: - Flow layout helper

private struct FlowLayout<Data: RandomAccessCollection, Content: View>: View where Data.Element: Hashable {
    let data: Data
    let content: (Data.Element) -> Content

    @State private var totalHeight: CGFloat = .zero

    var body: some View {
        GeometryReader { geo in
            generateContent(in: geo)
        }
        .frame(height: totalHeight)
    }

    private func generateContent(in geo: GeometryProxy) -> some View {
        var width = CGFloat.zero
        var height = CGFloat.zero

        return ZStack(alignment: .topLeading) {
            ForEach(Array(data.enumerated()), id: \.element) { _, item in
                content(item)
                    .alignmentGuide(.leading) { d in
                        if abs(width - d.width) > geo.size.width {
                            width = 0; height -= d.height + 6
                        }
                        let result = width
                        if item == data.last { width = 0 } else { width -= d.width + 6 }
                        return result
                    }
                    .alignmentGuide(.top) { _ in
                        let result = height
                        if item == data.last { height = 0 }
                        return result
                    }
            }
        }
        .background(viewHeightReader($totalHeight))
    }

    private func viewHeightReader(_ binding: Binding<CGFloat>) -> some View {
        GeometryReader { geo -> Color in
            DispatchQueue.main.async { binding.wrappedValue = geo.size.height }
            return .clear
        }
    }
}

#Preview {
    NavigationStack {
        DeviceDetailView(device: Device(
            id: "esp32-01",
            name: "Node Alpha",
            status: .online,
            firmwareVersion: "1.2.3",
            ipAddress: "192.168.1.101",
            macAddress: "AA:BB:CC:DD:EE:FF",
            capabilities: ["wifi", "ble", "gpio", "ota"]
        ))
    }
}
