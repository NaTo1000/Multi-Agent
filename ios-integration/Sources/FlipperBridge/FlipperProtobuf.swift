import Foundation

// MARK: - Command types

/// Flipper RPC command IDs (matches the Flipper protobuf schema).
public enum FlipperCommandType: UInt8 {
    case storageListRequest  = 0x62
    case storageListResponse = 0x63
    case storageReadRequest  = 0x64
    case storageReadResponse = 0x65
    case storageWriteRequest = 0x66
    case storageWriteResponse = 0x67
    case storageDeleteRequest = 0x68
    case storageDeleteResponse = 0x69
    case appStateResponse    = 0x0B
    case systemPingRequest   = 0x01
    case systemPingResponse  = 0x02
}

// MARK: - Raw RPC frame

/// A raw Flipper RPC frame: 4-byte little-endian length prefix + payload.
public struct FlipperRPCFrame {
    public let commandId: UInt32
    public let hasNext: Bool
    public let commandType: FlipperCommandType
    public let payload: Data

    /// Encodes the frame into wire-format bytes.
    public func encode() -> Data {
        var result = Data()

        // Payload: [commandId: 4 bytes LE] + [flags: 1 byte] + [commandType: 1 byte] + payload
        var body = Data()
        var id = commandId.littleEndian
        body.append(contentsOf: withUnsafeBytes(of: &id) { Array($0) })
        body.append(hasNext ? 0x01 : 0x00)
        body.append(commandType.rawValue)
        body.append(payload)

        // 4-byte LE length prefix
        var length = UInt32(body.count).littleEndian
        result.append(contentsOf: withUnsafeBytes(of: &length) { Array($0) })
        result.append(body)
        return result
    }

    /// Decodes a frame from raw `data`, returning nil if the data is malformed.
    public static func decode(from data: Data) -> FlipperRPCFrame? {
        guard data.count >= 10 else { return nil }

        let lengthBytes = data[0..<4]
        let length = lengthBytes.withUnsafeBytes { $0.load(as: UInt32.self).littleEndian }
        guard data.count >= Int(length) + 4 else { return nil }

        let body = data[4..<(4 + Int(length))]
        let commandId = body[body.startIndex..<(body.startIndex + 4)]
            .withUnsafeBytes { $0.load(as: UInt32.self).littleEndian }
        let flags = body[body.startIndex + 4]
        let rawType = body[body.startIndex + 5]
        let payload = Data(body[(body.startIndex + 6)...])

        guard let type = FlipperCommandType(rawValue: rawType) else { return nil }
        return FlipperRPCFrame(
            commandId: commandId,
            hasNext: (flags & 0x01) != 0,
            commandType: type,
            payload: payload
        )
    }
}

// MARK: - Request helpers

/// Encodes a storage list request for `path`.
public func makeStorageListRequest(commandId: UInt32, path: String) -> Data {
    let pathData = path.data(using: .utf8) ?? Data()
    // Protobuf field 1 (path): tag 0x0A + varint length + bytes
    var payload = Data()
    payload.append(0x0A)
    payload.append(UInt8(pathData.count))
    payload.append(pathData)

    return FlipperRPCFrame(
        commandId: commandId,
        hasNext: false,
        commandType: .storageListRequest,
        payload: payload
    ).encode()
}

/// Encodes a storage read request for `path`.
public func makeStorageReadRequest(commandId: UInt32, path: String) -> Data {
    let pathData = path.data(using: .utf8) ?? Data()
    var payload = Data()
    payload.append(0x0A)
    payload.append(UInt8(pathData.count))
    payload.append(pathData)

    return FlipperRPCFrame(
        commandId: commandId,
        hasNext: false,
        commandType: .storageReadRequest,
        payload: payload
    ).encode()
}

/// Encodes a storage write request for `path` with `fileData`.
public func makeStorageWriteRequest(commandId: UInt32, path: String, fileData: Data, hasNext: Bool = false) -> [Data] {
    let pathData = path.data(using: .utf8) ?? Data()
    let chunkSize = 512
    var frames: [Data] = []

    // First chunk includes the path
    var firstPayload = Data()
    firstPayload.append(0x0A)
    firstPayload.append(UInt8(pathData.count))
    firstPayload.append(pathData)
    let firstChunk = fileData.prefix(chunkSize)
    firstPayload.append(0x12)
    firstPayload.append(UInt8(firstChunk.count))
    firstPayload.append(contentsOf: firstChunk)

    let moreChunks = fileData.count > chunkSize
    frames.append(FlipperRPCFrame(
        commandId: commandId,
        hasNext: moreChunks,
        commandType: .storageWriteRequest,
        payload: firstPayload
    ).encode())

    // Subsequent chunks
    var offset = chunkSize
    while offset < fileData.count {
        let end = min(offset + chunkSize, fileData.count)
        let chunk = fileData[offset..<end]
        var payload = Data()
        payload.append(0x12)
        payload.append(UInt8(chunk.count))
        payload.append(contentsOf: chunk)
        frames.append(FlipperRPCFrame(
            commandId: commandId,
            hasNext: end < fileData.count,
            commandType: .storageWriteRequest,
            payload: payload
        ).encode())
        offset = end
    }

    return frames
}

/// Encodes a storage delete request for `path`.
public func makeStorageDeleteRequest(commandId: UInt32, path: String, recursive: Bool = false) -> Data {
    let pathData = path.data(using: .utf8) ?? Data()
    var payload = Data()
    payload.append(0x0A)
    payload.append(UInt8(pathData.count))
    payload.append(pathData)
    if recursive {
        payload.append(0x10)  // field 2 bool
        payload.append(0x01)
    }
    return FlipperRPCFrame(
        commandId: commandId,
        hasNext: false,
        commandType: .storageDeleteRequest,
        payload: payload
    ).encode()
}

// MARK: - Response parsers

/// Parses a storage list response payload into a list of file entries.
/// Format: repeated FileInfo messages (field 1 = name string, field 2 = type enum, field 3 = size int64)
public struct FileInfo {
    public let name: String
    public let isDirectory: Bool
    public let size: Int64
}

public func parseStorageListResponse(_ payload: Data) -> [FileInfo] {
    var results: [FileInfo] = []
    var index = payload.startIndex

    while index < payload.endIndex {
        guard index < payload.endIndex else { break }
        let tag = payload[index]; index = payload.index(after: index)
        let fieldNumber = tag >> 3
        let wireType = tag & 0x07

        switch (fieldNumber, wireType) {
        case (1, 2): // name (length-delimited)
            guard index < payload.endIndex else { return results }
            let len = Int(payload[index]); index = payload.index(after: index)
            guard payload.distance(from: index, to: payload.endIndex) >= len else { return results }
            let nameEnd = payload.index(index, offsetBy: len)
            let name = String(data: payload[index..<nameEnd], encoding: .utf8) ?? ""
            results.append(FileInfo(name: name, isDirectory: false, size: 0))
            index = nameEnd

        case (2, 0): // type (varint: 0 = file, 1 = dir)
            guard index < payload.endIndex else { return results }
            let typeVal = payload[index]; index = payload.index(after: index)
            if var last = results.last {
                results[results.count - 1] = FileInfo(
                    name: last.name,
                    isDirectory: typeVal == 1,
                    size: last.size
                )
            }

        case (3, 0): // size (varint)
            guard index < payload.endIndex else { return results }
            let sizeVal = Int64(payload[index]); index = payload.index(after: index)
            if var last = results.last {
                results[results.count - 1] = FileInfo(
                    name: last.name,
                    isDirectory: last.isDirectory,
                    size: sizeVal
                )
            }

        default:
            // Skip unknown fields
            if wireType == 2 {
                guard index < payload.endIndex else { return results }
                let skip = Int(payload[index]); index = payload.index(after: index)
                let skipEnd = payload.index(index, offsetBy: min(skip, payload.distance(from: index, to: payload.endIndex)))
                index = skipEnd
            } else {
                index = payload.index(after: index)
            }
        }
    }
    return results
}
