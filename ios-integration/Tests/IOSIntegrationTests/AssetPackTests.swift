import XCTest
@testable import IOSIntegration

final class AssetPackTests: XCTestCase {

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    // MARK: - AssetPackSummary decoding

    func testAssetPackSummaryDecoding() throws {
        let json = """
        [
            {
                "id": "pack-001",
                "name": "Rainbow Pack",
                "author": "dev_a",
                "preview_url": "https://cdn.example.com/packs/rainbow/preview.png",
                "source_url": "https://cdn.example.com/packs/rainbow"
            },
            {
                "id": "pack-002",
                "name": "Pixel Pack",
                "author": "dev_b",
                "source_url": "https://cdn.example.com/packs/pixel"
            }
        ]
        """.data(using: .utf8)!

        let packs = try decoder.decode([AssetPackSummary].self, from: json)
        XCTAssertEqual(packs.count, 2)
        XCTAssertEqual(packs[0].id, "pack-001")
        XCTAssertEqual(packs[0].name, "Rainbow Pack")
        XCTAssertNotNil(packs[0].previewURL)
        XCTAssertNil(packs[1].previewURL)
    }

    // MARK: - AssetPack with animations

    func testAssetPackWithAnimations() throws {
        let json = """
        {
            "id": "pack-03",
            "name": "Retro Pack",
            "author": "retro_dev",
            "description": "Retro style animations",
            "source_url": "https://cdn.example.com/packs/retro",
            "previews": [],
            "animations": [
                {
                    "name": "CRT_Boot",
                    "width": 128,
                    "height": 64,
                    "frame_count": 30,
                    "frame_rate": 15,
                    "passive_frames": [0,1,2,3,4],
                    "active_frames": [5,6,7,8,9,10]
                },
                {
                    "name": "Scan_Lines",
                    "width": 128,
                    "height": 64,
                    "frame_count": 8,
                    "frame_rate": 4,
                    "passive_frames": [0,1,2,3],
                    "active_frames": [4,5,6,7]
                }
            ],
            "meta_version": 2
        }
        """.data(using: .utf8)!

        let pack = try decoder.decode(AssetPack.self, from: json)
        XCTAssertEqual(pack.animations.count, 2)
        XCTAssertEqual(pack.animations[0].name, "CRT_Boot")
        XCTAssertEqual(pack.animations[0].duration, 2.0, accuracy: 0.001)
        XCTAssertEqual(pack.animations[1].frameRate, 4)
        XCTAssertEqual(pack.metaVersion, 2)
    }

    // MARK: - Animation duration computation

    func testAnimationDuration() {
        let anim = Animation(name: "Test", width: 128, height: 64, frameCount: 24, frameRate: 12)
        XCTAssertEqual(anim.duration, 2.0, accuracy: 0.001)
    }

    func testAnimationDurationZeroFrameRate() {
        let anim = Animation(name: "ZeroFPS", width: 128, height: 64, frameCount: 10, frameRate: 0)
        XCTAssertEqual(anim.duration, 0)
    }

    // MARK: - meta.json round-trip

    func testAnimationEncodingDecoding() throws {
        let original = Animation(
            name: "WaveMotion",
            width: 128,
            height: 64,
            frameCount: 16,
            frameRate: 8,
            passiveFrames: [0, 1, 2, 3],
            activeFrames: [4, 5, 6, 7],
            minFirmware: "0.90"
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)
        let decoded = try decoder.decode(Animation.self, from: data)

        XCTAssertEqual(decoded.name, original.name)
        XCTAssertEqual(decoded.frameCount, original.frameCount)
        XCTAssertEqual(decoded.passiveFrames, original.passiveFrames)
        XCTAssertEqual(decoded.activeFrames, original.activeFrames)
        XCTAssertEqual(decoded.minFirmware, "0.90")
    }

    // MARK: - FlipperDevice model

    func testFlipperDeviceIdentifiable() {
        let d1 = FlipperDevice(id: "uuid-1", name: "F1", address: "addr1")
        let d2 = FlipperDevice(id: "uuid-2", name: "F2", address: "addr2")
        XCTAssertNotEqual(d1.id, d2.id)
    }

    // MARK: - AssetPackError descriptions

    func testAssetPackErrorDescriptions() {
        XCTAssertNotNil(AssetPackError.fetchFailed(underlying: URLError(.notConnectedToInternet)).errorDescription)
        XCTAssertNotNil(AssetPackError.missingMetaJSON(packName: "TestPack").errorDescription)
        XCTAssertNotNil(AssetPackError.downloadFailed(underlying: URLError(.timedOut)).errorDescription)
    }
}
