import Foundation

// MARK: - Protocol

public protocol AssetPackServiceProtocol: Sendable {
    func fetchAvailablePacks() async throws -> [AssetPackSummary]
    func downloadPack(from summary: AssetPackSummary, progress: @escaping @Sendable (Double) -> Void) async throws -> AssetPack
    func installPack(_ pack: AssetPack, to destinationRoot: URL) async throws
}

// MARK: - Error

public enum AssetPackError: Error, LocalizedError, Sendable {
    case fetchFailed(underlying: Error)
    case missingMetaJSON(packName: String)
    case invalidMetaJSON(underlying: Error)
    case downloadFailed(underlying: Error)
    case installFailed(underlying: Error)

    public var errorDescription: String? {
        switch self {
        case .fetchFailed(let err):       return "Failed to fetch pack index: \(err.localizedDescription)"
        case .missingMetaJSON(let name):  return "meta.json not found in pack '\(name)'"
        case .invalidMetaJSON(let err):   return "Could not parse meta.json: \(err.localizedDescription)"
        case .downloadFailed(let err):    return "Pack download failed: \(err.localizedDescription)"
        case .installFailed(let err):     return "Install failed: \(err.localizedDescription)"
        }
    }
}

// MARK: - meta.json schema

/// Directly mirrors the `meta.json` schema used by the Momentum / iNFINITE_FLIPZ CDN.
private struct PackMeta: Decodable {
    let name: String
    let author: String
    let description: String?
    let metaVersion: Int?
    let animations: [AnimationMeta]

    private enum CodingKeys: String, CodingKey {
        case name, author, description
        case metaVersion = "meta_version"
        case animations
    }

    struct AnimationMeta: Decodable {
        let name: String
        let width: Int
        let height: Int
        let frameCount: Int
        let frameRate: Int
        let passiveFrames: [Int]?
        let activeFrames: [Int]?
        let path: String?
        let minFirmware: String?

        private enum CodingKeys: String, CodingKey {
            case name, width, height, path
            case frameCount   = "frame_count"
            case frameRate    = "frame_rate"
            case passiveFrames = "passive_frames"
            case activeFrames  = "active_frames"
            case minFirmware  = "min_firmware"
        }
    }
}

// MARK: - Implementation

/// Fetches Momentum / Flipper asset packs from the CDN, parses `meta.json`,
/// and installs them into the Flipper SD card layout on-disk.
public actor AssetPackService: AssetPackServiceProtocol {

    /// Base URL of the Momentum CDN asset-pack index.
    private static let cdnBase = URL(string: "https://up.momentum-fw.dev/asset-packs")!

    private let session: URLSession
    private let decoder: JSONDecoder

    public init(session: URLSession = .shared) {
        self.session = session
        self.decoder = JSONDecoder()
    }

    // MARK: - Public API

    /// Retrieves the CDN index and maps each entry to an `AssetPackSummary`.
    public func fetchAvailablePacks() async throws -> [AssetPackSummary] {
        let indexURL = Self.cdnBase.appendingPathComponent("index.json")
        do {
            let (data, _) = try await session.data(from: indexURL)
            return try decoder.decode([AssetPackSummary].self, from: data)
        } catch {
            throw AssetPackError.fetchFailed(underlying: error)
        }
    }

    /// Downloads and parses a full asset pack (including `meta.json`) from the CDN.
    public func downloadPack(
        from summary: AssetPackSummary,
        progress: @escaping @Sendable (Double) -> Void
    ) async throws -> AssetPack {
        let metaURL = summary.sourceURL.appendingPathComponent("meta.json")
        let (metaData, _): (Data, URLResponse)
        do {
            (metaData, _) = try await session.data(from: metaURL)
        } catch {
            throw AssetPackError.downloadFailed(underlying: error)
        }

        let meta: PackMeta
        do {
            meta = try decoder.decode(PackMeta.self, from: metaData)
        } catch {
            throw AssetPackError.invalidMetaJSON(underlying: error)
        }

        let animations = meta.animations.map { a in
            Animation(
                name: a.name,
                width: a.width,
                height: a.height,
                frameCount: a.frameCount,
                frameRate: a.frameRate,
                passiveFrames: a.passiveFrames ?? [],
                activeFrames: a.activeFrames ?? [],
                path: a.path,
                minFirmware: a.minFirmware
            )
        }

        // Download preview images (best-effort; non-fatal on failure)
        var previews: [URL] = []
        let previewURL = summary.sourceURL.appendingPathComponent("preview.png")
        if (try? await session.data(from: previewURL)) != nil {
            previews = [previewURL]
        }

        progress(1.0)

        return AssetPack(
            id: summary.id,
            name: meta.name,
            author: meta.author,
            description: meta.description ?? "",
            sourceURL: summary.sourceURL,
            previews: previews,
            animations: animations,
            metaVersion: meta.metaVersion
        )
    }

    /// Installs an asset pack under `destinationRoot/asset_packs/<pack.name>/`.
    /// Each animation folder is created and a `meta.json` file is written.
    public func installPack(_ pack: AssetPack, to destinationRoot: URL) async throws {
        let fm = FileManager.default
        let packDir = destinationRoot
            .appendingPathComponent("asset_packs")
            .appendingPathComponent(pack.name)

        do {
            try fm.createDirectory(at: packDir, withIntermediateDirectories: true)

            // Write top-level manifest
            let manifest = AssetPackManifest(from: pack)
            let manifestData = try JSONEncoder().encode(manifest)
            let manifestURL = packDir.appendingPathComponent("meta.json")
            try manifestData.write(to: manifestURL, options: .atomic)

            // Create placeholder directories for each animation
            for animation in pack.animations {
                let animDir = packDir.appendingPathComponent(animation.name)
                try fm.createDirectory(at: animDir, withIntermediateDirectories: true)
            }
        } catch {
            throw AssetPackError.installFailed(underlying: error)
        }
    }
}

// MARK: - Manifest encoder helper

private struct AssetPackManifest: Encodable {
    let name: String
    let author: String
    let description: String
    let metaVersion: Int?
    let animations: [[String: String]]

    init(from pack: AssetPack) {
        self.name = pack.name
        self.author = pack.author
        self.description = pack.description
        self.metaVersion = pack.metaVersion
        self.animations = pack.animations.map { ["name": $0.name] }
    }

    private enum CodingKeys: String, CodingKey {
        case name, author, description, animations
        case metaVersion = "meta_version"
    }
}
