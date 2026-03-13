import Foundation
import os.log

/// Centralised `os.Logger` instances for the Multi-Agent iOS integration.
///
/// Usage:
/// ```swift
/// AppLogger.app.info("App launched")
/// AppLogger.telemetry.debug("Frame received: \(frame.deviceId)")
/// AppLogger.ble.error("BLE connection lost")
/// ```
public enum AppLogger {

    private static let subsystem = "com.multiagent.ios"

    /// General application events.
    public static let app        = Logger(subsystem: subsystem, category: "app")

    /// WebSocket telemetry stream events.
    public static let telemetry  = Logger(subsystem: subsystem, category: "telemetry")

    /// CoreBluetooth / Flipper BLE events.
    public static let ble        = Logger(subsystem: subsystem, category: "ble")

    /// WiFi Pineapple API events.
    public static let pineapple  = Logger(subsystem: subsystem, category: "pineapple")

    /// Firmware download and OTA events.
    public static let firmware   = Logger(subsystem: subsystem, category: "firmware")

    /// Asset pack CDN and install events.
    public static let assets     = Logger(subsystem: subsystem, category: "assets")

    /// Networking / URLSession events.
    public static let network    = Logger(subsystem: subsystem, category: "network")

    /// Security / Keychain events.
    public static let security   = Logger(subsystem: subsystem, category: "security")
}
