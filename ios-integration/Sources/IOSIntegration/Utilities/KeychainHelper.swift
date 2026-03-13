import Foundation
import KeychainAccess

/// Thin wrapper around `KeychainAccess` for storing sensitive values
/// (API tokens, Pineapple keys) outside the app's `UserDefaults`.
public final class KeychainHelper: @unchecked Sendable {

    public static let shared = KeychainHelper()

    // MARK: - Well-known keys

    public static let apiTokenKey      = "multiagent.api_token"
    public static let pineappleKeyKey  = "multiagent.pineapple_api_key"

    // MARK: - Private

    private let keychain: Keychain

    private init() {
        keychain = Keychain(service: "com.multiagent.ios")
            .accessibility(.afterFirstUnlock)
    }

    // MARK: - Public API

    /// Stores `value` under `key` in the Keychain.  Returns `false` on failure.
    @discardableResult
    public func store(key: String, value: String) -> Bool {
        do {
            try keychain.set(value, key: key)
            return true
        } catch {
            AppLogger.app.error("Keychain write failed for key '\(key)': \(error)")
            return false
        }
    }

    /// Reads and returns the value stored for `key`, or `nil` if absent.
    public func read(key: String) -> String? {
        do {
            return try keychain.getString(key)
        } catch {
            AppLogger.app.error("Keychain read failed for key '\(key)': \(error)")
            return nil
        }
    }

    /// Removes the value stored for `key`.
    @discardableResult
    public func delete(key: String) -> Bool {
        do {
            try keychain.remove(key)
            return true
        } catch {
            AppLogger.app.error("Keychain delete failed for key '\(key)': \(error)")
            return false
        }
    }

    /// Returns `true` if a non-empty value exists for `key`.
    public func contains(key: String) -> Bool {
        read(key: key) != nil
    }
}
