import Foundation
import CryptoKit

// MARK: - Protocol

public protocol FirmwareServiceProtocol: Sendable {
    func listReleases() async throws -> [FirmwareRelease]
    func download(release: FirmwareRelease, progress: @escaping @Sendable (Double) -> Void) async throws -> URL
    func flash(release: FirmwareRelease, deviceIds: [String]) async throws
}

// MARK: - Error

public enum FirmwareError: Error, LocalizedError, Sendable {
    case listFailed(underlying: Error)
    case downloadFailed(underlying: Error)
    case checksumMismatch(expected: String, actual: String)
    case flashFailed(underlying: Error)

    public var errorDescription: String? {
        switch self {
        case .listFailed(let err):     return "Failed to list firmware: \(err.localizedDescription)"
        case .downloadFailed(let err): return "Download failed: \(err.localizedDescription)"
        case .checksumMismatch(let e, let a): return "Checksum mismatch — expected \(e), got \(a)"
        case .flashFailed(let err):    return "Flash failed: \(err.localizedDescription)"
        }
    }
}

// MARK: - Implementation

/// Downloads and validates OTA firmware builds from the Multi-Agent backend.
public actor FirmwareService: FirmwareServiceProtocol {

    private let config: AppConfig
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(config: AppConfig = .shared) {
        self.config = config
        self.session = config.makeSession()

        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Public API

    public func listReleases() async throws -> [FirmwareRelease] {
        let url = config.baseURL.appendingPathComponent(Endpoints.firmwareBuilds)
        var req = URLRequest(url: url)
        authorise(&req)

        do {
            let (data, _) = try await session.data(for: req)
            return try decoder.decode([FirmwareRelease].self, from: data)
        } catch let err as DecodingError {
            throw FirmwareError.listFailed(underlying: err)
        } catch {
            throw FirmwareError.listFailed(underlying: error)
        }
    }

    /// Downloads the firmware binary to a temporary file, validates its SHA-256 checksum,
    /// and returns the local file URL.
    public func download(
        release: FirmwareRelease,
        progress: @escaping @Sendable (Double) -> Void
    ) async throws -> URL {
        let destination = FileManager.default.temporaryDirectory
            .appendingPathComponent("firmware_\(release.version).bin")

        if FileManager.default.fileExists(atPath: destination.path) {
            // Verify cached copy is still valid before reusing
            if let data = try? Data(contentsOf: destination),
               SHA256Helper.hexDigest(of: data) == release.sha256 {
                progress(1.0)
                return destination
            }
            try? FileManager.default.removeItem(at: destination)
        }

        var req = URLRequest(url: release.url)
        authorise(&req)

        let (asyncBytes, response) = try await session.bytes(for: req)
        let totalBytes = (response as? HTTPURLResponse)?
            .value(forHTTPHeaderField: "Content-Length")
            .flatMap(Int.init) ?? 0

        var downloaded = Data()
        var received = 0

        for try await byte in asyncBytes {
            downloaded.append(byte)
            received += 1
            if totalBytes > 0 {
                progress(Double(received) / Double(totalBytes))
            }
        }

        // Checksum validation
        let digest = SHA256Helper.hexDigest(of: downloaded)
        guard digest == release.sha256 else {
            throw FirmwareError.checksumMismatch(expected: release.sha256, actual: digest)
        }

        try downloaded.write(to: destination, options: .atomic)
        progress(1.0)
        return destination
    }

    /// Instructs the backend to OTA-flash `release` onto the given devices.
    public func flash(release: FirmwareRelease, deviceIds: [String]) async throws {
        let url = config.baseURL.appendingPathComponent(Endpoints.firmwareFlash)
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        authorise(&req)

        let payload = FirmwareFlashRequest(firmwareId: release.id, deviceIds: deviceIds)
        do {
            req.httpBody = try encoder.encode(payload)
            let (_, response) = try await session.data(for: req)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            if !(200...299).contains(code) {
                throw FirmwareError.flashFailed(
                    underlying: OrchestratorError.httpError(statusCode: code, body: "")
                )
            }
        } catch let err as FirmwareError {
            throw err
        } catch {
            throw FirmwareError.flashFailed(underlying: error)
        }
    }

    // MARK: - Private

    private func authorise(_ req: inout URLRequest) {
        if let token = KeychainHelper.shared.read(key: KeychainHelper.apiTokenKey) {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
    }
}
