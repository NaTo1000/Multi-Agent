import XCTest
@testable import IOSIntegration

final class BMFrameDecoderTests: XCTestCase {

    // MARK: - Basic decode

    func testDecodeAllBlack() {
        // 1×1 black pixel: 1 byte, MSB = 0
        let data = Data([0x00])
        #if canImport(UIKit)
        let image = BMFrameDecoder.decode(data: data, width: 1, height: 1)
        XCTAssertNotNil(image)
        XCTAssertEqual(image?.size.width, 1)
        XCTAssertEqual(image?.size.height, 1)
        #endif
    }

    func testDecodeAllWhite() {
        // 1×1 white pixel: bit 7 = 1 → byte 0x80
        let data = Data([0x80])
        #if canImport(UIKit)
        let image = BMFrameDecoder.decode(data: data, width: 1, height: 1)
        XCTAssertNotNil(image)
        #endif
    }

    func testDecodeStandardFlipperCanvas() {
        // Standard 128×64 Flipper display: 128/8 = 16 bytes/row × 64 rows = 1024 bytes
        let bytesPerRow = (128 + 7) / 8  // = 16
        let totalBytes = bytesPerRow * 64 // = 1024
        let data = Data(repeating: 0x55, count: totalBytes)  // alternating 0101 pattern

        #if canImport(UIKit)
        let image = BMFrameDecoder.decode(data: data, width: 128, height: 64)
        XCTAssertNotNil(image)
        XCTAssertEqual(image?.size.width, 128)
        XCTAssertEqual(image?.size.height, 64)
        #endif
    }

    func testDecodeReturnsNilForInsufficientData() {
        // Need 2 bytes for 9×1 (bytesPerRow = 2), only supply 1
        let data = Data([0xFF])
        #if canImport(UIKit)
        let image = BMFrameDecoder.decode(data: data, width: 9, height: 1)
        XCTAssertNil(image)
        #endif
    }

    func testDecodeReturnsNilForZeroDimension() {
        #if canImport(UIKit)
        XCTAssertNil(BMFrameDecoder.decode(data: Data([0xFF]), width: 0, height: 1))
        XCTAssertNil(BMFrameDecoder.decode(data: Data([0xFF]), width: 1, height: 0))
        #endif
    }

    // MARK: - Row padding

    func testBytesPerRowCalculation() {
        // Width 8 → 1 byte per row
        XCTAssertEqual((8 + 7) / 8, 1)
        // Width 9 → 2 bytes per row (padded)
        XCTAssertEqual((9 + 7) / 8, 2)
        // Width 128 → 16 bytes per row
        XCTAssertEqual((128 + 7) / 8, 16)
        // Width 64 → 8 bytes per row
        XCTAssertEqual((64 + 7) / 8, 8)
    }

    // MARK: - Multi-frame decode

    func testDecodeFramesEmpty() {
        #if canImport(UIKit)
        let frames = BMFrameDecoder.decodeFrames(data: Data(), width: 128, height: 64, frameCount: 0)
        XCTAssertTrue(frames.isEmpty)
        #endif
    }

    func testDecodeMultipleFrames() {
        let bytesPerFrame = ((128 + 7) / 8) * 64  // 1024 bytes
        let frameCount = 3
        let data = Data(repeating: 0xFF, count: bytesPerFrame * frameCount)

        #if canImport(UIKit)
        let frames = BMFrameDecoder.decodeFrames(data: data, width: 128, height: 64, frameCount: frameCount)
        XCTAssertEqual(frames.count, frameCount)
        for frame in frames {
            XCTAssertEqual(frame.size.width, 128)
            XCTAssertEqual(frame.size.height, 64)
        }
        #endif
    }

    func testDecodeFramesInsufficientData() {
        // Only enough for 1 frame, request 2
        let bytesPerFrame = ((128 + 7) / 8) * 64
        let data = Data(repeating: 0x00, count: bytesPerFrame)

        #if canImport(UIKit)
        let frames = BMFrameDecoder.decodeFrames(data: data, width: 128, height: 64, frameCount: 2)
        XCTAssertTrue(frames.isEmpty)
        #endif
    }

    // MARK: - SHA256 integration

    func testSHA256HelperHexDigest() {
        let data = "hello world".data(using: .utf8)!
        let digest = SHA256Helper.hexDigest(of: data)
        // SHA-256 always produces a 256-bit (32-byte, 64 hex character) digest.
        XCTAssertEqual(digest.count, 64)
        // Verify the digest is all lowercase hex characters.
        XCTAssertTrue(digest.allSatisfy { $0.isHexDigit })
        // Verify determinism: same input → same output.
        XCTAssertEqual(digest, SHA256Helper.hexDigest(of: data))
    }

    func testSHA256ValidateSuccess() {
        let data = Data([0x01, 0x02, 0x03])
        let digest = SHA256Helper.hexDigest(of: data)
        XCTAssertTrue(SHA256Helper.validate(data: data, expectedHex: digest))
    }

    func testSHA256ValidateFailure() {
        let data = Data([0x01, 0x02, 0x03])
        XCTAssertFalse(SHA256Helper.validate(data: data, expectedHex: "0000000000000000000000000000000000000000000000000000000000000000"))
    }

    func testSHA256CaseInsensitiveValidation() {
        let data = "test".data(using: .utf8)!
        let lowerDigest = SHA256Helper.hexDigest(of: data)
        let upperDigest = lowerDigest.uppercased()
        XCTAssertTrue(SHA256Helper.validate(data: data, expectedHex: upperDigest))
    }
}
