import Foundation

// MARK: - Protocol

public protocol AssetPackManagerProtocol: Sendable {
    func fetchAvailable() async throws -> [AssetPackSummary]
    func install(pack: AssetPackSummary, progress: @escaping @Sendable (Double) -> Void) async throws
    func listInstalled() -> [InstalledPack]
    func remove(packId: String) throws
}

// MARK: - Types

/// Metadata stored locally for an installed asset pack.
public struct InstalledPack: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let author: String
    public let installedAt: Date
    public let installPath: URL
    public let animationCount: Int

    private enum CodingKeys: String, CodingKey {
        case id, name, author, animationCount
        case installedAt  = "installed_at"
        case installPath  = "install_path"
    }
}

/// A parsed `meta.json` manifest from an asset pack.
public struct PackManifest: Codable, Sendable {
    public let name: String
    public let author: String
    public let description: String?
    public let metaVersion: Int?
    public let animations: [AnimationEntry]

    public struct AnimationEntry: Codable, Sendable {
        public let name: String
        public let width: Int
        public let height: Int
        public let frameCount: Int
        public let frameRate: Int

        private enum CodingKeys: String, CodingKey {
            case name, width, height
            case frameCount  = "frame_count"
            case frameRate   = "frame_rate"
        }
    }

    private enum CodingKeys: String, CodingKey {
        case name, author, description, animations
        case metaVersion = "meta_version"
    }
}

// MARK: - Implementation

/// Coordinates fetching, parsing, installing, and removing Flipper Zero asset packs.
public actor AssetPackManager: AssetPackManagerProtocol {

    private static let cdnIndexURL = URL(string: "https://up.momentum-fw.dev/asset-packs/index.json")!
    private static let registryFilename = "installed_packs.json"

    private let installRoot: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    /// Registry of installed packs, persisted to disk.
    private var registry: [String: InstalledPack] = [:]

    public init(
        installRoot: URL = FileManager.default
            .urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("FlipperPacks"),
        session: URLSession = .shared
    ) {
        self.installRoot = installRoot
        self.session = session
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
        self.encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    }

    // MARK: - Public API

    public func fetchAvailable() async throws -> [AssetPackSummary] {
        let (data, _) = try await session.data(from: Self.cdnIndexURL)
        return try decoder.decode([AssetPackSummary].self, from: data)
    }

    public func install(pack summary: AssetPackSummary, progress: @escaping @Sendable (Double) -> Void) async throws {
        try createDirectoryIfNeeded(installRoot)
        loadRegistry()

        // Download meta.json
        let metaURL = summary.sourceURL.appendingPathComponent("meta.json")
        progress(0.1)
        let (metaData, _) = try await session.data(from: metaURL)
        let manifest = try decoder.decode(PackManifest.self, from: metaData)
        progress(0.3)

        // Create pack directory
        let packDir = installRoot.appendingPathComponent(manifest.name)
        try createDirectoryIfNeeded(packDir)

        // Write meta.json
        let manifestURL = packDir.appendingPathComponent("meta.json")
        try metaData.write(to: manifestURL, options: .atomic)
        progress(0.5)

        // Create animation subdirectories
        for anim in manifest.animations {
            let animDir = packDir.appendingPathComponent(anim.name)
            try createDirectoryIfNeeded(animDir)
        }
        progress(0.8)

        // Update registry
        let installed = InstalledPack(
            id: summary.id,
            name: manifest.name,
            author: manifest.author,
            installedAt: Date(),
            installPath: packDir,
            animationCount: manifest.animations.count
        )
        registry[summary.id] = installed
        saveRegistry()
        progress(1.0)
    }

    public func listInstalled() -> [InstalledPack] {
        loadRegistry()
        return Array(registry.values).sorted { $0.installedAt > $1.installedAt }
    }

    public func remove(packId: String) throws {
        loadRegistry()
        guard let pack = registry[packId] else { return }
        if FileManager.default.fileExists(atPath: pack.installPath.path) {
            try FileManager.default.removeItem(at: pack.installPath)
        }
        registry.removeValue(forKey: packId)
        saveRegistry()
    }

    // MARK: - Private

    private func createDirectoryIfNeeded(_ url: URL) throws {
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }

    private var registryURL: URL {
        installRoot.appendingPathComponent(Self.registryFilename)
    }

    private func loadRegistry() {
        guard let data = try? Data(contentsOf: registryURL),
              let decoded = try? decoder.decode([String: InstalledPack].self, from: data) else {
            return
        }
        registry = decoded
    }

    private func saveRegistry() {
        try? encoder.encode(registry).write(to: registryURL, options: .atomic)
    }
}

// MARK: - AssetPackSummary (local stub for standalone AssetPackManager)

public struct AssetPackSummary: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let author: String
    public let previewURL: URL?
    public let sourceURL: URL

    private enum CodingKeys: String, CodingKey {
        case id, name, author
        case previewURL = "preview_url"
        case sourceURL  = "source_url"
    }

    public init(id: String, name: String, author: String, previewURL: URL?, sourceURL: URL) {
        self.id = id; self.name = name; self.author = author
        self.previewURL = previewURL; self.sourceURL = sourceURL
    }
}
