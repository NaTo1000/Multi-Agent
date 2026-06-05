import Foundation

/// Drives the asset pack browser: fetches summaries, tracks downloads, manages installs.
@MainActor
public final class AssetPackViewModel: ObservableObject {

    // MARK: - Published state

    @Published public var packs: [AssetPackSummary] = []
    @Published public var downloadProgress: [String: Double] = [:]
    @Published public var installedPackIds: Set<String> = []
    @Published public var isLoading = false
    @Published public var searchText: String = ""
    @Published public var showError = false
    @Published public var errorMessage: String?

    // MARK: - Derived

    public var filteredPacks: [AssetPackSummary] {
        guard !searchText.isEmpty else { return packs }
        let q = searchText.lowercased()
        return packs.filter {
            $0.name.lowercased().contains(q) ||
            $0.author.lowercased().contains(q)
        }
    }

    // MARK: - Services

    private let packService: AssetPackService
    private let installRoot: URL

    public init(
        packService: AssetPackService = AssetPackService(),
        installRoot: URL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    ) {
        self.packService = packService
        self.installRoot = installRoot
        loadInstalledIds()
    }

    // MARK: - Public API

    public func fetchPacks() async {
        isLoading = true
        defer { isLoading = false }
        do {
            packs = try await packService.fetchAvailablePacks()
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    public func install(pack summary: AssetPackSummary) async {
        downloadProgress[summary.id] = 0

        do {
            let fullPack = try await packService.downloadPack(from: summary) { [weak self] p in
                Task { @MainActor [weak self] in
                    self?.downloadProgress[summary.id] = p
                }
            }
            try await packService.installPack(fullPack, to: installRoot)
            installedPackIds.insert(summary.id)
            downloadProgress.removeValue(forKey: summary.id)
            persistInstalledIds()
        } catch {
            downloadProgress.removeValue(forKey: summary.id)
            errorMessage = error.localizedDescription
            showError = true
        }
    }

    // MARK: - Persistence

    private static let installedKey = "installed_asset_packs"

    private func loadInstalledIds() {
        let saved = UserDefaults.standard.stringArray(forKey: Self.installedKey) ?? []
        installedPackIds = Set(saved)
    }

    private func persistInstalledIds() {
        UserDefaults.standard.set(Array(installedPackIds), forKey: Self.installedKey)
    }
}
