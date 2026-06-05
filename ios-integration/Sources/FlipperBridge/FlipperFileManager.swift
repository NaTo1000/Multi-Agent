import Foundation

/// High-level SD card file operations for a connected Flipper Zero.
/// Uses `FlipperBLEManager` for transport and `FlipperProtobuf` for message encoding.
public final class FlipperFileManager {

    private let bleManager: FlipperBLEManager
    private var commandIdCounter: UInt32 = 1

    public init(bleManager: FlipperBLEManager) {
        self.bleManager = bleManager
    }

    // MARK: - Public API

    /// Lists files and directories at `path` on the Flipper SD card.
    public func listFiles(at path: String) async throws -> [FlipperFile] {
        let commandId = nextCommandId()
        let requestData = makeStorageListRequest(commandId: commandId, path: path)
        try await bleManager.send(data: requestData)

        let responseData = try await waitForResponse(commandId: commandId)
        guard let frame = FlipperRPCFrame.decode(from: responseData),
              frame.commandType == .storageListResponse else {
            throw FlipperFileError.unexpectedResponse
        }

        let entries = parseStorageListResponse(frame.payload)
        return entries.map { entry in
            FlipperFile(
                path: "\(path)/\(entry.name)".replacingOccurrences(of: "//", with: "/"),
                name: entry.name,
                isDirectory: entry.isDirectory,
                size: entry.isDirectory ? nil : Int(entry.size)
            )
        }
    }

    /// Reads the contents of the file at `path` and returns raw `Data`.
    public func readFile(at path: String) async throws -> Data {
        let commandId = nextCommandId()
        let requestData = makeStorageReadRequest(commandId: commandId, path: path)
        try await bleManager.send(data: requestData)

        var accumulated = Data()
        var hasNext = true

        while hasNext {
            let chunk = try await waitForResponse(commandId: commandId)
            guard let frame = FlipperRPCFrame.decode(from: chunk) else {
                throw FlipperFileError.malformedFrame
            }
            // Payload field 2 is the file data bytes
            let fileChunk = extractFileData(from: frame.payload)
            accumulated.append(fileChunk)
            hasNext = frame.hasNext
        }

        return accumulated
    }

    /// Writes `data` to the file at `path` on the Flipper SD card.
    public func writeFile(_ data: Data, to path: String) async throws {
        let commandId = nextCommandId()
        let frames = makeStorageWriteRequest(commandId: commandId, path: path, fileData: data)

        for frame in frames {
            try await bleManager.send(data: frame)
        }

        _ = try await waitForResponse(commandId: commandId)
    }

    /// Deletes the file (or directory) at `path`.
    public func deleteFile(at path: String, recursive: Bool = false) async throws {
        let commandId = nextCommandId()
        let requestData = makeStorageDeleteRequest(commandId: commandId, path: path, recursive: recursive)
        try await bleManager.send(data: requestData)
        _ = try await waitForResponse(commandId: commandId)
    }

    // MARK: - Private

    private func nextCommandId() -> UInt32 {
        defer { commandIdCounter &+= 1 }
        return commandIdCounter
    }

    /// Waits for a response frame that matches `commandId`, with a 10-second timeout.
    private func waitForResponse(commandId: UInt32) async throws -> Data {
        try await withThrowingTaskGroup(of: Data.self) { group in
            group.addTask { [weak self] in
                guard let self else { throw FlipperFileError.managerDeallocated }
                for await data in self.bleManager.receivedDataStream() {
                    if let frame = FlipperRPCFrame.decode(from: data),
                       frame.commandId == commandId {
                        return data
                    }
                }
                throw FlipperFileError.streamEnded
            }

            group.addTask {
                try await Task.sleep(for: .seconds(10))
                throw FlipperFileError.timeout
            }

            let result = try await group.next()!
            group.cancelAll()
            return result
        }
    }

    /// Extracts raw file bytes from a storage read response payload (field 2, wire type 2).
    private func extractFileData(from payload: Data) -> Data {
        var index = payload.startIndex
        while index < payload.endIndex {
            let tag = payload[index]; index = payload.index(after: index)
            let fieldNumber = tag >> 3
            let wireType = tag & 0x07
            if fieldNumber == 2 && wireType == 2 {
                guard index < payload.endIndex else { return Data() }
                let len = Int(payload[index]); index = payload.index(after: index)
                guard payload.distance(from: index, to: payload.endIndex) >= len else { return Data() }
                return Data(payload[index..<payload.index(index, offsetBy: len)])
            } else if wireType == 2 {
                guard index < payload.endIndex else { return Data() }
                let skip = Int(payload[index]); index = payload.index(after: index)
                index = payload.index(index, offsetBy: min(skip, payload.distance(from: index, to: payload.endIndex)))
            } else {
                guard index < payload.endIndex else { return Data() }
                index = payload.index(after: index)
            }
        }
        return Data()
    }
}

// MARK: - Error

public enum FlipperFileError: Error, LocalizedError {
    case unexpectedResponse
    case malformedFrame
    case timeout
    case streamEnded
    case managerDeallocated

    public var errorDescription: String? {
        switch self {
        case .unexpectedResponse:   return "Unexpected RPC response type from Flipper."
        case .malformedFrame:       return "Could not decode RPC frame."
        case .timeout:              return "Flipper RPC response timed out."
        case .streamEnded:          return "BLE data stream ended unexpectedly."
        case .managerDeallocated:   return "BLE manager was deallocated."
        }
    }
}

// MARK: - FlipperFile (local re-export from IOSIntegration module)
// The FlipperBridge module mirrors the model for standalone use.

public struct FlipperFile: Identifiable {
    public var id: String { path }
    public let path: String
    public let name: String
    public let isDirectory: Bool
    public let size: Int?

    public init(path: String, name: String, isDirectory: Bool, size: Int? = nil) {
        self.path = path
        self.name = name
        self.isDirectory = isDirectory
        self.size = size
    }
}
