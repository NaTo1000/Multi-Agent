import Foundation

/// A single Flipper Zero / Momentum animation entry from a `meta.json` manifest.
public struct Animation: Codable, Identifiable, Sendable {
    public var id: String { name }

    public let name: String
    /// Canvas width in pixels (standard Flipper display is 128 px wide).
    public let width: Int
    /// Canvas height in pixels (standard Flipper display is 64 px tall).
    public let height: Int
    /// Total number of frames in the sequence.
    public let frameCount: Int
    /// Playback speed in frames per second.
    public let frameRate: Int
    /// Total animation duration in seconds (computed = frameCount / frameRate).
    public var duration: Double { frameCount > 0 && frameRate > 0 ? Double(frameCount) / Double(frameRate) : 0 }
    /// Frame indices that play when the device is in the passive (idle) state.
    public let passiveFrames: [Int]
    /// Frame indices that play when the device is in the active (interaction) state.
    public let activeFrames: [Int]
    /// Relative path to the animation folder inside the asset pack.
    public let path: String?
    /// Minimum firmware version required to display this animation.
    public let minFirmware: String?

    private enum CodingKeys: String, CodingKey {
        case name
        case width
        case height
        case frameCount   = "frame_count"
        case frameRate    = "frame_rate"
        case passiveFrames = "passive_frames"
        case activeFrames  = "active_frames"
        case path
        case minFirmware  = "min_firmware"
    }

    public init(
        name: String,
        width: Int,
        height: Int,
        frameCount: Int,
        frameRate: Int,
        passiveFrames: [Int] = [],
        activeFrames: [Int] = [],
        path: String? = nil,
        minFirmware: String? = nil
    ) {
        self.name = name
        self.width = width
        self.height = height
        self.frameCount = frameCount
        self.frameRate = frameRate
        self.passiveFrames = passiveFrames
        self.activeFrames = activeFrames
        self.path = path
        self.minFirmware = minFirmware
    }
}
