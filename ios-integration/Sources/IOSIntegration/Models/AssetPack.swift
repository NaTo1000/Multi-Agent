import Foundation

/// A Flipper Zero / Momentum asset pack containing animations, fonts, and icons.
public struct AssetPack: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let author: String
    public let description: String
    /// CDN URL to the pack's root directory (contains `meta.json`).
    public let sourceURL: URL
    /// Preview image URLs (thumbnails shown in the browser).
    public let previews: [URL]
    /// Animation entries declared in `meta.json`.
    public let animations: [Animation]
    /// Pack format version from `meta.json`.
    public let metaVersion: Int?

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case author
        case description
        case sourceURL   = "source_url"
        case previews
        case animations
        case metaVersion = "meta_version"
    }

    public init(
        id: String,
        name: String,
        author: String,
        description: String,
        sourceURL: URL,
        previews: [URL] = [],
        animations: [Animation] = [],
        metaVersion: Int? = nil
    ) {
        self.id = id
        self.name = name
        self.author = author
        self.description = description
        self.sourceURL = sourceURL
        self.previews = previews
        self.animations = animations
        self.metaVersion = metaVersion
    }
}

/// Lightweight summary returned by the Momentum CDN index before a full pack download.
public struct AssetPackSummary: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let author: String
    public let previewURL: URL?
    public let sourceURL: URL

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case author
        case previewURL = "preview_url"
        case sourceURL  = "source_url"
    }
}
