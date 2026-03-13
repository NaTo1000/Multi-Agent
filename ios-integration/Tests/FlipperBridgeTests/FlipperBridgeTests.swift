import XCTest
@testable import FlipperBridge

final class FlipperBridgeTests: XCTestCase {

    // MARK: - RPC Frame encoding/decoding

    func testFrameEncodeDecodeRoundTrip() {
        let payload = "Hello Flipper".data(using: .utf8)!
        let original = FlipperRPCFrame(
            commandId: 42,
            hasNext: false,
            commandType: .systemPingRequest,
            payload: payload
        )

        let encoded = original.encode()
        let decoded = FlipperRPCFrame.decode(from: encoded)

        XCTAssertNotNil(decoded)
        XCTAssertEqual(decoded?.commandId, 42)
        XCTAssertEqual(decoded?.hasNext, false)
        XCTAssertEqual(decoded?.commandType, .systemPingRequest)
        XCTAssertEqual(decoded?.payload, payload)
    }

    func testFrameWithHasNextFlag() {
        let frame = FlipperRPCFrame(
            commandId: 99,
            hasNext: true,
            commandType: .storageReadResponse,
            payload: Data()
        )
        let encoded = frame.encode()
        let decoded = FlipperRPCFrame.decode(from: encoded)

        XCTAssertEqual(decoded?.hasNext, true)
    }

    func testFrameDecodeReturnNilForTooShortData() {
        XCTAssertNil(FlipperRPCFrame.decode(from: Data()))
        XCTAssertNil(FlipperRPCFrame.decode(from: Data([0x00, 0x01])))
    }

    // MARK: - Storage list request

    func testMakeStorageListRequest() {
        let data = makeStorageListRequest(commandId: 1, path: "/ext")
        XCTAssertFalse(data.isEmpty)

        // Should decode to a valid frame
        let frame = FlipperRPCFrame.decode(from: data)
        XCTAssertNotNil(frame)
        XCTAssertEqual(frame?.commandType, .storageListRequest)
        XCTAssertEqual(frame?.commandId, 1)
    }

    func testMakeStorageReadRequest() {
        let data = makeStorageReadRequest(commandId: 2, path: "/ext/badusb/test.txt")
        let frame = FlipperRPCFrame.decode(from: data)
        XCTAssertNotNil(frame)
        XCTAssertEqual(frame?.commandType, .storageReadRequest)
    }

    func testMakeStorageDeleteRequest() {
        let data = makeStorageDeleteRequest(commandId: 3, path: "/ext/temp.txt", recursive: false)
        let frame = FlipperRPCFrame.decode(from: data)
        XCTAssertNotNil(frame)
        XCTAssertEqual(frame?.commandType, .storageDeleteRequest)
    }

    // MARK: - Storage write request (multi-chunk)

    func testMakeStorageWriteRequestSingleChunk() {
        let fileData = "Small file".data(using: .utf8)!
        let frames = makeStorageWriteRequest(commandId: 4, path: "/ext/test.txt", fileData: fileData)
        XCTAssertEqual(frames.count, 1)

        let frame = FlipperRPCFrame.decode(from: frames[0])
        XCTAssertNotNil(frame)
        XCTAssertEqual(frame?.commandType, .storageWriteRequest)
        XCTAssertEqual(frame?.hasNext, false)
    }

    func testMakeStorageWriteRequestMultipleChunks() {
        // Create data larger than 512 bytes to force chunking
        let fileData = Data(repeating: 0xAB, count: 1100)
        let frames = makeStorageWriteRequest(commandId: 5, path: "/ext/large.bin", fileData: fileData)
        XCTAssertGreaterThan(frames.count, 1)

        // All frames except the last should have hasNext = true
        for (i, frameData) in frames.enumerated() {
            if let frame = FlipperRPCFrame.decode(from: frameData) {
                if i < frames.count - 1 {
                    XCTAssertTrue(frame.hasNext, "Frame \(i) should have hasNext=true")
                } else {
                    XCTAssertFalse(frame.hasNext, "Last frame should have hasNext=false")
                }
            }
        }
    }

    // MARK: - Storage list response parsing

    func testParseStorageListResponseEmpty() {
        let entries = parseStorageListResponse(Data())
        XCTAssertTrue(entries.isEmpty)
    }

    func testParseStorageListResponseSingleEntry() {
        // Build a minimal protobuf-like payload with a name field (field 1, wire type 2)
        var payload = Data()
        let name = "test.txt".data(using: .utf8)!
        payload.append(0x0A)                    // field 1, wire type 2 (length-delimited)
        payload.append(UInt8(name.count))        // length
        payload.append(contentsOf: name)         // bytes

        let entries = parseStorageListResponse(payload)
        XCTAssertEqual(entries.count, 1)
        XCTAssertEqual(entries[0].name, "test.txt")
    }

    // MARK: - BLE UUIDs

    func testFlipperUUIDsAreDistinct() {
        let uuids = [
            FlipperUUIDs.serviceUUID,
            FlipperUUIDs.txCharacteristic,
            FlipperUUIDs.rxCharacteristic,
            FlipperUUIDs.flowControlChar,
            FlipperUUIDs.batteryService,
            FlipperUUIDs.batteryLevel
        ]
        let unique = Set(uuids.map(\.uuidString))
        XCTAssertEqual(unique.count, uuids.count)
    }

    // MARK: - DFU

    func testParseDFUFileTooSmall() {
        let tinyData = Data([0x00, 0x01, 0x02])
        let result = FlipperDFUManager.parseDFUFile(tinyData)
        XCTAssertNil(result)
    }

    func testParseDFURawBinary() {
        let binaryData = Data(repeating: 0xFF, count: 64_000)  // 64 KB fake firmware
        let result = FlipperDFUManager.parseDFUFile(binaryData)
        XCTAssertNotNil(result)
        XCTAssertEqual(result?.applicationData?.count, binaryData.count)
    }

    func testDFUImageTotalSize() {
        let image = DFUImage(
            softDeviceData: Data(count: 1000),
            bootloaderData: Data(count: 500),
            applicationData: Data(count: 256_000),
            initPacket: nil,
            version: "1.0.0"
        )
        XCTAssertEqual(image.totalSize, 257_500)
    }

    // MARK: - FlipperBLE error descriptions

    func testBLEErrorDescriptions() {
        XCTAssertNotNil(FlipperBLEError.notPoweredOn.errorDescription)
        XCTAssertNotNil(FlipperBLEError.notConnected.errorDescription)
        XCTAssertNotNil(FlipperBLEError.peripheralNotFound("uuid").errorDescription)
        XCTAssertNotNil(FlipperBLEError.connectionFailed.errorDescription)
    }

    // MARK: - FlipperFileError descriptions

    func testFileErrorDescriptions() {
        XCTAssertNotNil(FlipperFileError.unexpectedResponse.errorDescription)
        XCTAssertNotNil(FlipperFileError.malformedFrame.errorDescription)
        XCTAssertNotNil(FlipperFileError.timeout.errorDescription)
    }
}
