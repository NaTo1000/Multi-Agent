import Foundation
import CryptoKit

/// Convenience wrappers around `CryptoKit.SHA256` for file and data checksum validation.
public enum SHA256Helper {

    // MARK: - Data digest

    /// Returns the lower-case hex-encoded SHA-256 digest of `data`.
    public static func hexDigest(of data: Data) -> String {
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    /// Returns the raw `SHA256.Digest` for `data`.
    public static func digest(of data: Data) -> SHA256.Digest {
        SHA256.hash(data: data)
    }

    // MARK: - File digest

    /// Computes and returns the lower-case hex-encoded SHA-256 digest for the file at `url`.
    /// Reads the file in streaming 512 KB chunks to avoid loading large binaries into memory.
    ///
    /// - Throws: File-system errors from `FileHandle`.
    public static func hexDigest(ofFileAt url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }

        var hasher = SHA256()
        let chunkSize = 512 * 1_024  // 512 KB

        while true {
            let chunk: Data
            if #available(iOS 13.4, macOS 10.15.4, *) {
                guard let c = try handle.read(upToCount: chunkSize), !c.isEmpty else { break }
                chunk = c
            } else {
                let c = handle.readData(ofLength: chunkSize)
                guard !c.isEmpty else { break }
                chunk = c
            }
            hasher.update(data: chunk)
        }

        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    // MARK: - Validation

    /// Returns `true` if `data` matches the provided `expectedHex` SHA-256 checksum.
    public static func validate(data: Data, expectedHex: String) -> Bool {
        hexDigest(of: data).lowercased() == expectedHex.lowercased()
    }

    /// Returns `true` if the file at `url` matches the provided `expectedHex` checksum.
    public static func validate(fileAt url: URL, expectedHex: String) -> Bool {
        guard let actual = try? hexDigest(ofFileAt: url) else { return false }
        return actual.lowercased() == expectedHex.lowercased()
    }
}
