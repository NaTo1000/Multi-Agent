import SwiftUI

/// Displays a scrollable list of ESP32 devices with status indicators and pull-to-refresh.
public struct DeviceListView: View {
    @StateObject private var viewModel = DeviceListViewModel()

    public init() {}

    public var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.devices.isEmpty {
                    ProgressView("Loading devices…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if viewModel.devices.isEmpty {
                    ContentUnavailableView(
                        "No Devices",
                        systemImage: "cpu",
                        description: Text("No ESP32 devices have been registered yet.")
                    )
                } else {
                    List {
                        ForEach(viewModel.devices) { device in
                            NavigationLink(destination: DeviceDetailView(device: device)) {
                                DeviceRowView(device: device)
                            }
                        }
                        .onDelete(perform: viewModel.deleteDevices)
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Devices")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        viewModel.showAddDevice = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .searchable(text: $viewModel.searchText, prompt: "Search devices")
            .refreshable {
                await viewModel.fetchDevices()
            }
            .task {
                await viewModel.fetchDevices()
            }
            .alert("Error", isPresented: $viewModel.showError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
            .sheet(isPresented: $viewModel.showAddDevice) {
                AddDeviceSheet(viewModel: viewModel)
            }
        }
    }
}

// MARK: - Row

private struct DeviceRowView: View {
    let device: Device

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(device.status.color)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                Text(device.name)
                    .font(.headline)
                HStack(spacing: 6) {
                    if let ip = device.ipAddress {
                        Text(ip)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    if let fw = device.firmwareVersion {
                        Text("v\(fw)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Spacer()

            Text(device.status.rawValue.capitalized)
                .font(.caption.bold())
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(device.status.color.opacity(0.15), in: Capsule())
                .foregroundStyle(device.status.color)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Add Device Sheet

private struct AddDeviceSheet: View {
    @ObservedObject var viewModel: DeviceListViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var mac  = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Device Info") {
                    TextField("Name", text: $name)
                    TextField("MAC Address (optional)", text: $mac)
                }
            }
            .navigationTitle("Add Device")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        Task {
                            await viewModel.addDevice(name: name, mac: mac.isEmpty ? nil : mac)
                            dismiss()
                        }
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }
}

// MARK: - Color helper

extension Device.DeviceStatus {
    var color: Color {
        switch self {
        case .online:  return .green
        case .offline: return .gray
        case .busy:    return .orange
        case .error:   return .red
        }
    }
}

#Preview {
    DeviceListView()
}
