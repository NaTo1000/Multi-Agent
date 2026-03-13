import SwiftUI
import Charts

/// Frequency scan visualization for sub-GHz, WiFi, and BLE bands.
public struct FrequencyView: View {
    @StateObject private var viewModel = FrequencyViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    bandPickerSection
                    spectrumChartSection
                    channelListSection
                }
                .padding()
            }
            .navigationTitle("Frequency Scanner")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        Task { await viewModel.scan() }
                    } label: {
                        if viewModel.isScanning {
                            ProgressView().controlSize(.small)
                        } else {
                            Label("Scan", systemImage: "antenna.radiowaves.left.and.right")
                        }
                    }
                    .disabled(viewModel.isScanning)
                }
            }
            .task {
                await viewModel.scan()
            }
        }
    }

    // MARK: - Band picker

    private var bandPickerSection: some View {
        Picker("Band", selection: $viewModel.selectedBand) {
            ForEach(FrequencyViewModel.Band.allCases, id: \.self) { band in
                Text(band.displayName).tag(band)
            }
        }
        .pickerStyle(.segmented)
    }

    // MARK: - Spectrum chart

    private var spectrumChartSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Signal Strength", systemImage: "waveform.path")
                .font(.headline)

            if viewModel.chartData.isEmpty {
                Text(viewModel.isScanning ? "Scanning…" : "No data — tap Scan")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 150)
            } else {
                Chart(viewModel.chartData) { point in
                    BarMark(
                        x: .value("Channel", point.channel),
                        y: .value("dBm", point.signal)
                    )
                    .foregroundStyle(signalColor(point.signal))
                    .cornerRadius(3)
                }
                .frame(height: 200)
                .chartXAxis {
                    AxisMarks(values: .stride(by: viewModel.xStride)) { value in
                        AxisValueLabel()
                    }
                }
                .chartYAxis {
                    AxisMarks { value in
                        AxisGridLine()
                        AxisValueLabel()
                    }
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Channel list

    private var channelListSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Detected Networks", systemImage: "list.bullet")
                .font(.headline)

            ForEach(viewModel.detectedNetworks) { network in
                HStack {
                    VStack(alignment: .leading) {
                        Text(network.ssid.isEmpty ? "(hidden)" : network.ssid)
                            .font(.subheadline.bold())
                        Text("ch \(network.channel) · \(network.bssid)")
                            .font(.caption.monospaced())
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text("\(network.signal) dBm")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(signalColor(network.signal))
                }
                Divider()
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Helpers

    private func signalColor(_ dBm: Int) -> Color {
        switch dBm {
        case -50...0:   return .green
        case -65 ... -51: return .yellow
        case -75 ... -66: return .orange
        default:        return .red
        }
    }
}

// MARK: - ViewModel

@MainActor
private class FrequencyViewModel: ObservableObject {

    enum Band: String, CaseIterable {
        case wifi24  = "2.4 GHz"
        case wifi5   = "5 GHz"
        case ble     = "BLE"
        case subGHz  = "Sub-GHz"

        var displayName: String { rawValue }
    }

    struct ChartPoint: Identifiable {
        let id = UUID()
        let channel: Int
        let signal: Int
    }

    @Published var selectedBand: Band = .wifi24
    @Published var chartData: [ChartPoint] = []
    @Published var detectedNetworks: [NetworkScan] = []
    @Published var isScanning = false

    var xStride: Double { selectedBand == .wifi24 ? 1 : 4 }

    func scan() async {
        isScanning = true
        defer { isScanning = false }

        // In a real implementation, this would drive a CoreWLAN / CoreBluetooth / SDR scan.
        // For demo purposes we generate plausible mock data.
        try? await Task.sleep(for: .seconds(0.5))

        switch selectedBand {
        case .wifi24:
            chartData = (1...14).map { ch in
                ChartPoint(channel: ch, signal: Int.random(in: -90 ... -30))
            }
            detectedNetworks = (1...6).map { i in
                NetworkScan(
                    ssid: "Network_\(i)",
                    bssid: "AA:BB:CC:DD:EE:\(String(format: "%02X", i))",
                    channel: [1, 6, 11].randomElement()!,
                    signal: Int.random(in: -75 ... -40),
                    encryption: .wpa2
                )
            }

        case .wifi5:
            let channels = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 149, 153, 157, 161]
            chartData = channels.map { ch in
                ChartPoint(channel: ch, signal: Int.random(in: -90 ... -35))
            }
            detectedNetworks = []

        case .ble:
            chartData = (37...39).map { ch in
                ChartPoint(channel: ch, signal: Int.random(in: -80 ... -40))
            }
            detectedNetworks = []

        case .subGHz:
            chartData = stride(from: 300, through: 950, by: 25).map { freq in
                ChartPoint(channel: freq, signal: Int.random(in: -120 ... -60))
            }
            detectedNetworks = []
        }
    }
}

#Preview {
    FrequencyView()
}
