import Foundation
import CoreBluetooth

// MARK: - Known Flipper Zero BLE UUIDs

public enum FlipperUUIDs {
    /// Primary service advertised by the Flipper Zero.
    public static let serviceUUID           = CBUUID(string: "19ED82AE-ED21-4C9D-4145-228E62FE0000")
    /// RPC TX characteristic (phone → Flipper).
    public static let txCharacteristic      = CBUUID(string: "19ED82AE-ED21-4C9D-4145-228E62FE0001")
    /// RPC RX characteristic (Flipper → phone).
    public static let rxCharacteristic      = CBUUID(string: "19ED82AE-ED21-4C9D-4145-228E62FE0002")
    /// Flow control characteristic.
    public static let flowControlChar       = CBUUID(string: "19ED82AE-ED21-4C9D-4145-228E62FE0003")
    /// Battery service (standard BLE 0x180F).
    public static let batteryService        = CBUUID(string: "180F")
    public static let batteryLevel          = CBUUID(string: "2A19")
}

// MARK: - Protocol

public protocol FlipperBLEManagerProtocol: Sendable {
    func startScan() async
    func stopScan()
    func connect(to device: FlipperDevice) async throws
    func disconnect() async
    func send(data: Data) async throws
    func discoveredDeviceStream() -> AsyncStream<FlipperDevice>
}

// MARK: - BLE Manager

/// Manages CoreBluetooth scanning, connection, and RPC channel with a Flipper Zero.
public final class FlipperBLEManager: NSObject, FlipperBLEManagerProtocol,
                                       CBCentralManagerDelegate, CBPeripheralDelegate {

    private var central: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var txChar: CBCharacteristic?
    private var rxChar: CBCharacteristic?

    // Continuations for async bridging
    private var connectContinuation: CheckedContinuation<Void, Error>?
    private var discoveryContinuations: [UUID: AsyncStream<FlipperDevice>.Continuation] = [:]
    private var receivedDataContinuations: [UUID: AsyncStream<Data>.Continuation] = [:]

    private let queue = DispatchQueue(label: "com.multiagent.flipper.ble", qos: .userInitiated)

    override public init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: queue)
    }

    // MARK: - Scanning

    public func startScan() async {
        guard central.state == .poweredOn else { return }
        central.scanForPeripherals(
            withServices: [FlipperUUIDs.serviceUUID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]
        )
    }

    public func stopScan() {
        central.stopScan()
    }

    public func discoveredDeviceStream() -> AsyncStream<FlipperDevice> {
        let id = UUID()
        return AsyncStream { [weak self] continuation in
            continuation.onTermination = { [weak self] _ in
                self?.discoveryContinuations.removeValue(forKey: id)
            }
            self?.discoveryContinuations[id] = continuation
        }
    }

    // MARK: - Connection

    public func connect(to device: FlipperDevice) async throws {
        guard let peripheral = central.retrievePeripherals(
            withIdentifiers: [UUID(uuidString: device.id)!]
        ).first else {
            throw FlipperBLEError.peripheralNotFound(device.id)
        }

        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            connectContinuation = cont
            central.connect(peripheral, options: nil)
        }
    }

    public func disconnect() async {
        if let peripheral = connectedPeripheral {
            central.cancelPeripheralConnection(peripheral)
        }
        connectedPeripheral = nil
        txChar = nil
        rxChar = nil
    }

    // MARK: - RPC

    public func send(data: Data) async throws {
        guard let peripheral = connectedPeripheral,
              let char = txChar else {
            throw FlipperBLEError.notConnected
        }
        let mtu = peripheral.maximumWriteValueLength(for: .withResponse)
        var offset = 0
        while offset < data.count {
            let end = min(offset + mtu, data.count)
            let chunk = data[offset..<end]
            peripheral.writeValue(Data(chunk), for: char, type: .withResponse)
            offset = end
            // Small yield to let CoreBluetooth process
            try await Task.sleep(for: .milliseconds(20))
        }
    }

    public func receivedDataStream() -> AsyncStream<Data> {
        let id = UUID()
        return AsyncStream { [weak self] continuation in
            continuation.onTermination = { [weak self] _ in
                self?.receivedDataContinuations.removeValue(forKey: id)
            }
            self?.receivedDataContinuations[id] = continuation
        }
    }

    // MARK: - CBCentralManagerDelegate

    public func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            // Ready to scan
        }
    }

    public func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        let name = peripheral.name ?? "Flipper (\(peripheral.identifier.uuidString.prefix(8)))"
        let device = FlipperDevice(
            id: peripheral.identifier.uuidString,
            name: name,
            address: peripheral.identifier.uuidString,
            isConnected: false
        )
        for continuation in discoveryContinuations.values {
            continuation.yield(device)
        }
    }

    public func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        connectedPeripheral = peripheral
        peripheral.delegate = self
        peripheral.discoverServices([FlipperUUIDs.serviceUUID, FlipperUUIDs.batteryService])
    }

    public func centralManager(
        _ central: CBCentralManager,
        didFailToConnect peripheral: CBPeripheral,
        error: Error?
    ) {
        connectContinuation?.resume(throwing: error ?? FlipperBLEError.connectionFailed)
        connectContinuation = nil
    }

    public func centralManager(
        _ central: CBCentralManager,
        didDisconnectPeripheral peripheral: CBPeripheral,
        error: Error?
    ) {
        connectedPeripheral = nil
        txChar = nil
        rxChar = nil
    }

    // MARK: - CBPeripheralDelegate

    public func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil else {
            connectContinuation?.resume(throwing: error!)
            connectContinuation = nil
            return
        }
        for service in peripheral.services ?? [] {
            if service.uuid == FlipperUUIDs.serviceUUID {
                peripheral.discoverCharacteristics(
                    [FlipperUUIDs.txCharacteristic, FlipperUUIDs.rxCharacteristic, FlipperUUIDs.flowControlChar],
                    for: service
                )
            }
        }
    }

    public func peripheral(
        _ peripheral: CBPeripheral,
        didDiscoverCharacteristicsFor service: CBService,
        error: Error?
    ) {
        guard error == nil else {
            connectContinuation?.resume(throwing: error!)
            connectContinuation = nil
            return
        }

        for char in service.characteristics ?? [] {
            switch char.uuid {
            case FlipperUUIDs.txCharacteristic:
                txChar = char
            case FlipperUUIDs.rxCharacteristic:
                rxChar = char
                peripheral.setNotifyValue(true, for: char)
            default:
                break
            }
        }

        // Once both TX and RX are found, signal connection success
        if txChar != nil && rxChar != nil {
            connectContinuation?.resume()
            connectContinuation = nil
        }
    }

    public func peripheral(
        _ peripheral: CBPeripheral,
        didUpdateValueFor characteristic: CBCharacteristic,
        error: Error?
    ) {
        guard error == nil, let data = characteristic.value else { return }
        for continuation in receivedDataContinuations.values {
            continuation.yield(data)
        }
    }
}

// MARK: - Error

public enum FlipperBLEError: Error, LocalizedError {
    case notPoweredOn
    case notConnected
    case peripheralNotFound(String)
    case connectionFailed
    case sendFailed

    public var errorDescription: String? {
        switch self {
        case .notPoweredOn:            return "Bluetooth is not powered on."
        case .notConnected:            return "No Flipper device is connected."
        case .peripheralNotFound(let id): return "Peripheral not found: \(id)"
        case .connectionFailed:        return "BLE connection failed."
        case .sendFailed:              return "Failed to send data over BLE."
        }
    }
}
