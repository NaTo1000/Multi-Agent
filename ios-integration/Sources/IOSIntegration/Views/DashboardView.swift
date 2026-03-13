import SwiftUI

/// Top-level dashboard showing fleet health, recent telemetry, and quick actions.
public struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    statusCardsRow
                    telemetrySummarySection
                    quickActionsSection
                }
                .padding()
            }
            .navigationTitle("Multi-Agent Dashboard")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    connectionIndicator
                }
            }
            .task {
                await viewModel.load()
            }
            .refreshable {
                await viewModel.load()
            }
            .alert("Error", isPresented: $viewModel.showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }

    // MARK: - Subviews

    private var statusCardsRow: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            StatCard(
                title: "Online",
                value: "\(viewModel.onlineCount)",
                color: .green,
                icon: "checkmark.circle.fill"
            )
            StatCard(
                title: "Offline",
                value: "\(viewModel.offlineCount)",
                color: .red,
                icon: "xmark.circle.fill"
            )
            StatCard(
                title: "Busy",
                value: "\(viewModel.busyCount)",
                color: .orange,
                icon: "clock.circle.fill"
            )
            StatCard(
                title: "Total",
                value: "\(viewModel.devices.count)",
                color: .blue,
                icon: "cpu.fill"
            )
        }
    }

    private var telemetrySummarySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Recent Telemetry", systemImage: "waveform")
                .font(.headline)

            if viewModel.latestTelemetry.isEmpty {
                Text("No telemetry data yet")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 60)
            } else {
                ForEach(viewModel.latestTelemetry.prefix(5), id: \.deviceId) { frame in
                    TelemetryRowView(data: frame)
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var quickActionsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Quick Actions", systemImage: "bolt.fill")
                .font(.headline)

            HStack(spacing: 12) {
                ActionButton(title: "Refresh", icon: "arrow.clockwise") {
                    await viewModel.load()
                }
                ActionButton(title: "Reconnect WS", icon: "wifi") {
                    await viewModel.reconnectSocket()
                }
                ActionButton(title: "Dispatch", icon: "paperplane.fill") {
                    await viewModel.dispatchBroadcast()
                }
            }
        }
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var connectionIndicator: some View {
        Circle()
            .fill(viewModel.connectionState == .connected ? Color.green : Color.red)
            .frame(width: 10, height: 10)
    }
}

// MARK: - Helper sub-views

private struct StatCard: View {
    let title: String
    let value: String
    let color: Color
    let icon: String

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)
            Text(value)
                .font(.title.bold())
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct TelemetryRowView: View {
    let data: TelemetryData

    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(data.deviceId)
                    .font(.caption.bold())
                Text(data.eventType ?? "heartbeat")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            ForEach(data.metrics.sorted(by: { $0.key < $1.key }).prefix(2), id: \.key) { key, val in
                VStack(alignment: .trailing) {
                    Text(String(format: "%.1f", val))
                        .font(.caption.monospacedDigit())
                    Text(key)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
        Divider()
    }
}

private struct ActionButton: View {
    let title: String
    let icon: String
    let action: () async -> Void

    var body: some View {
        Button {
            Task { await action() }
        } label: {
            VStack(spacing: 4) {
                Image(systemName: icon)
                Text(title)
                    .font(.caption2)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(Color.accentColor.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    DashboardView()
}
