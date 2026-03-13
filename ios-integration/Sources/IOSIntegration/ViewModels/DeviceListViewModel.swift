import Foundation

/// Drives the device list screen — fetches, searches, adds, and removes devices.
@MainActor
public final class DeviceListViewModel: ObservableObject {

    // MARK: - Published state

    @Published public var devices: [Device] = []
    @Published public var searchText: String = ""
    @Published public var isLoading = false
    @Published public var showError = false
    @Published public var errorMessage: String?
    @Published public var showAddDevice = false

    // MARK: - Derived

    public var filteredDevices: [Device] {
        guard !searchText.isEmpty else { return devices }
        let q = searchText.lowercased()
        return devices.filter {
            $0.name.lowercased().contains(q) ||
            $0.ipAddress?.lowercased().contains(q) == true ||
            $0.macAddress?.lowercased().contains(q) == true
        }
    }

    // MARK: - Services

    private let service: OrchestratorService

    public init(service: OrchestratorService = OrchestratorService()) {
        self.service = service
    }

    // MARK: - Public API

    public func fetchDevices() async {
        isLoading = true
        defer { isLoading = false }
        do {
            devices = try await service.fetchDevices()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func addDevice(name: String, mac: String?) async {
        let payload = DeviceCreate(name: name, macAddress: mac)
        do {
            let created = try await service.registerDevice(payload)
            devices.append(created)
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func deleteDevices(at offsets: IndexSet) {
        let toDelete = offsets.map { devices[$0] }
        devices.remove(atOffsets: offsets)
        Task {
            for device in toDelete {
                try? await service.deleteDevice(id: device.id)
            }
        }
    }
}
