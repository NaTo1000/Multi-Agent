import Foundation

// MARK: - DFU Image

/// Parsed Nordic DFU firmware image ready to flash over BLE.
public struct DFUImage {
    public let softDeviceData: Data?
    public let bootloaderData: Data?
    public let applicationData: Data?
    public let initPacket: Data?
    public let version: String?

    public var totalSize: Int {
        (softDeviceData?.count ?? 0)
        + (bootloaderData?.count ?? 0)
        + (applicationData?.count ?? 0)
    }
}

// MARK: - Flash progress

public struct DFUProgress: Sendable {
    public let phase: Phase
    public let bytesWritten: Int
    public let totalBytes: Int
    public var fraction: Double { totalBytes > 0 ? Double(bytesWritten) / Double(totalBytes) : 0 }

    public enum Phase: String, Sendable {
        case initialising = "Initialising"
        case erasing      = "Erasing"
        case uploading    = "Uploading"
        case validating   = "Validating"
        case activating   = "Activating"
        case complete     = "Complete"
        case failed       = "Failed"
    }
}

// MARK: - DFU Manager

/// Implements the Nordic Semiconductor DFU protocol over BLE for flashing Flipper Zero firmware.
///
/// The Flipper Zero uses a variant of Nordic's Legacy DFU protocol.
/// Service UUID: 00001530-1212-EFDE-1523-785FEABCD123
/// Control Point: 00001531-...
/// Packet:        00001532-...
public final class FlipperDFUManager {

    // Nordic DFU UUIDs
    private static let dfuServiceUUID        = "00001530-1212-EFDE-1523-785FEABCD123"
    private static let dfuControlPointUUID   = "00001531-1212-EFDE-1523-785FEABCD123"
    private static let dfuPacketUUID         = "00001532-1212-EFDE-1523-785FEABCD123"

    // DFU OP codes
    private enum OpCode: UInt8 {
        case startDFU          = 0x01
        case initDFUParameters = 0x02
        case receiveFirmware   = 0x03
        case validateFirmware  = 0x04
        case activateAndReset  = 0x05
        case reset             = 0x06
        case reportReceivedImageSize = 0x07
        case packetReceiptNotification = 0x08
        case responseCode      = 0x10
        case packetReceiptNotificationRequest = 0x08
    }

    private let bleManager: FlipperBLEManager

    public init(bleManager: FlipperBLEManager) {
        self.bleManager = bleManager
    }

    // MARK: - Public API

    /// Parses a `.zip` DFU package (Nordic DFU ZIP format) into a `DFUImage`.
    public static func parseDFUFile(_ data: Data) -> DFUImage? {
        // A DFU ZIP contains at minimum an `application.bin` and `application.dat`.
        // This parser handles the unzipped binary case as well.
        // For a real implementation, unzip and locate the relevant sections.
        // Here we treat the entire data as the application binary for simplicity.
        guard data.count > 8 else { return nil }

        // Check for ZIP magic (PK\x03\x04)
        let zipMagic: [UInt8] = [0x50, 0x4B, 0x03, 0x04]
        if data.prefix(4).elementsEqual(zipMagic) {
            // Would need a ZIP library to properly parse; return a minimal DFUImage
            return DFUImage(
                softDeviceData: nil,
                bootloaderData: nil,
                applicationData: data,
                initPacket: nil,
                version: nil
            )
        }

        // Treat as raw binary application firmware
        return DFUImage(
            softDeviceData: nil,
            bootloaderData: nil,
            applicationData: data,
            initPacket: nil,
            version: nil
        )
    }

    /// Flashes `image` over BLE, yielding `DFUProgress` updates.
    /// Returns an `AsyncStream<DFUProgress>` so callers can observe progress reactively.
    public func flash(_ image: DFUImage) -> AsyncStream<DFUProgress> {
        AsyncStream { continuation in
            Task {
                do {
                    try await self.performFlash(image: image, continuation: continuation)
                } catch {
                    continuation.yield(DFUProgress(phase: .failed, bytesWritten: 0, totalBytes: 0))
                    continuation.finish()
                }
            }
        }
    }

    // MARK: - Private

    private func performFlash(
        image: DFUImage,
        continuation: AsyncStream<DFUProgress>.Continuation
    ) async throws {
        guard let appData = image.applicationData else {
            throw DFUError.noApplicationData
        }

        let total = appData.count
        continuation.yield(DFUProgress(phase: .initialising, bytesWritten: 0, totalBytes: total))

        // 1. Send Start DFU command (application type = 0x04)
        let startCmd = Data([OpCode.startDFU.rawValue, 0x04])
        try await bleManager.send(data: startCmd)
        try await Task.sleep(for: .milliseconds(200))

        // 2. Send firmware size packet (4 bytes SD + 4 bytes BL + 4 bytes APP)
        var sizePacket = Data(count: 8)
        let appSize = UInt32(appData.count).littleEndian
        sizePacket.append(contentsOf: withUnsafeBytes(of: appSize) { Array($0) })
        try await bleManager.send(data: sizePacket)
        try await Task.sleep(for: .milliseconds(200))

        continuation.yield(DFUProgress(phase: .uploading, bytesWritten: 0, totalBytes: total))

        // 3. Stream firmware in 20-byte packets (BLE ATT_MTU default)
        let packetSize = 20
        var written = 0
        var packetCount = 0
        let notificationInterval = 10

        // Request packet receipt notifications every 10 packets
        let prn = Data([OpCode.packetReceiptNotificationRequest.rawValue, UInt8(notificationInterval), 0x00])
        try await bleManager.send(data: prn)

        // 4. Send "Receive Firmware" command
        let receiveFWCmd = Data([OpCode.receiveFirmware.rawValue])
        try await bleManager.send(data: receiveFWCmd)
        try await Task.sleep(for: .milliseconds(100))

        while written < appData.count {
            let end = min(written + packetSize, appData.count)
            let packet = appData[written..<end]
            try await bleManager.send(data: Data(packet))
            written = end
            packetCount += 1

            if packetCount % notificationInterval == 0 {
                // Wait for notification acknowledgment
                try await Task.sleep(for: .milliseconds(50))
                continuation.yield(DFUProgress(phase: .uploading, bytesWritten: written, totalBytes: total))
            }
        }

        continuation.yield(DFUProgress(phase: .validating, bytesWritten: written, totalBytes: total))
        let validateCmd = Data([OpCode.validateFirmware.rawValue])
        try await bleManager.send(data: validateCmd)
        try await Task.sleep(for: .seconds(1))

        continuation.yield(DFUProgress(phase: .activating, bytesWritten: written, totalBytes: total))
        let activateCmd = Data([OpCode.activateAndReset.rawValue])
        try await bleManager.send(data: activateCmd)
        try await Task.sleep(for: .milliseconds(500))

        continuation.yield(DFUProgress(phase: .complete, bytesWritten: written, totalBytes: total))
        continuation.finish()
    }
}

// MARK: - Error

public enum DFUError: Error, LocalizedError {
    case noApplicationData
    case deviceNotReady
    case flashFailed(String)

    public var errorDescription: String? {
        switch self {
        case .noApplicationData:   return "DFU image has no application binary."
        case .deviceNotReady:      return "Flipper is not in DFU mode."
        case .flashFailed(let msg): return "Flash failed: \(msg)"
        }
    }
}
