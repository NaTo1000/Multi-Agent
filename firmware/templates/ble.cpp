/**
 * BLE 5 Feature Module
 *
 * Provides:
 * - BLE 5 advertising (2M PHY, extended advertising)
 * - GATT server with command characteristic
 * - BLE scan results
 * - Paired-app communication via custom service
 *
 * Service UUID: 6E400001-B5A3-F393-E0A9-E50E24DCCA9E (Nordic UART-compatible)
 * TX Char UUID: 6E400003-B5A3-F393-E0A9-E50E24DCCA9E
 * RX Char UUID: 6E400002-B5A3-F393-E0A9-E50E24DCCA9E
 */

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ArduinoJson.h>

#define BLE_SERVICE_UUID  "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define BLE_RX_UUID       "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define BLE_TX_UUID       "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

extern void handleCommand(const String& cmd, const JsonObject& payload,
                          JsonObject& response);

static BLEServer*         bleServer   = nullptr;
static BLECharacteristic* bleTxChar   = nullptr;
static bool               bleConnected = false;

// ---------------------------------------------------------------------------
// Server callbacks
// ---------------------------------------------------------------------------
class BLEServerCB : public BLEServerCallbacks {
    void onConnect(BLEServer* srv) override {
        bleConnected = true;
        Serial.println("[BLE] Client connected");
    }
    void onDisconnect(BLEServer* srv) override {
        bleConnected = false;
        Serial.println("[BLE] Client disconnected — restarting advertising");
        BLEDevice::startAdvertising();
    }
};

// ---------------------------------------------------------------------------
// RX characteristic callback — receives JSON commands from the paired app
// ---------------------------------------------------------------------------
class BLERxCB : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* ch) override {
        String value = ch->getValue().c_str();
        if (value.length() == 0) return;

        StaticJsonDocument<512> doc;
        if (deserializeJson(doc, value) != DeserializationError::Ok) {
            String err = "{\"error\":\"invalid json\"}";
            bleTxChar->setValue(err.c_str());
            bleTxChar->notify();
            return;
        }

        String command = doc["command"].as<String>();
        JsonObject payload = doc["payload"].as<JsonObject>();
        StaticJsonDocument<512> respDoc;
        JsonObject response = respDoc.to<JsonObject>();
        handleCommand(command, payload, response);

        String respStr;
        serializeJson(respDoc, respStr);
        bleTxChar->setValue(respStr.c_str());
        bleTxChar->notify();
    }
};

// ---------------------------------------------------------------------------
// BLE feature setup
// ---------------------------------------------------------------------------
void __attribute__((constructor)) bleFeatureSetup() {
    BLEDevice::init(DEVICE_NAME);

    // Enable BLE 5 2M PHY when the host supports it
    esp_ble_gap_set_prefered_default_phy(ESP_BLE_GAP_PHY_2M, ESP_BLE_GAP_PHY_2M);

    bleServer = BLEDevice::createServer();
    bleServer->setCallbacks(new BLEServerCB());

    BLEService* svc = bleServer->createService(BLE_SERVICE_UUID);

    // TX characteristic (notifications to phone)
    bleTxChar = svc->createCharacteristic(
        BLE_TX_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    bleTxChar->addDescriptor(new BLE2902());

    // RX characteristic (writes from phone)
    BLECharacteristic* rxChar = svc->createCharacteristic(
        BLE_RX_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    rxChar->setCallbacks(new BLERxCB());

    svc->start();

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(BLE_SERVICE_UUID);
    adv->setScanResponse(true);
    adv->setMinPreferred(0x06);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] Advertising as \"%s\"\n", DEVICE_NAME);
}
