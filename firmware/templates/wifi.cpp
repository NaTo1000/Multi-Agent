/**
 * WiFi Feature Module
 *
 * Provides:
 * - WiFi STA connection with retry logic
 * - mDNS registration (device accessible as <name>.local)
 * - HTTP command server (JSON API used by the orchestrator)
 * - OTA firmware update via HTTPUpdate
 * - RSSI reading
 *
 * Appended to base.cpp by FirmwareAgent when "wifi" feature is requested.
 */

#include <WiFi.h>
#include <WiFiClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <HTTPUpdate.h>
#include <ArduinoJson.h>

// ---------------------------------------------------------------------------
// Credentials (set via OTA config push or compile-time defines)
// ---------------------------------------------------------------------------
#ifndef WIFI_SSID
  #define WIFI_SSID ""
#endif
#ifndef WIFI_PASSWORD
  #define WIFI_PASSWORD ""
#endif

static WebServer httpServer(API_PORT);
static bool wifiConnected = false;

// ---------------------------------------------------------------------------
// Forward declare base.cpp function
// ---------------------------------------------------------------------------
extern void handleCommand(const String& cmd, const JsonObject& payload,
                          JsonObject& response);

// ---------------------------------------------------------------------------
// HTTP handler — POST /api/command
// ---------------------------------------------------------------------------
static void onApiCommand() {
    if (!httpServer.hasArg("plain")) {
        httpServer.send(400, "application/json", "{\"error\":\"no body\"}");
        return;
    }

    StaticJsonDocument<1024> doc;
    DeserializationError err = deserializeJson(doc, httpServer.arg("plain"));
    if (err) {
        httpServer.send(400, "application/json", "{\"error\":\"invalid json\"}");
        return;
    }

    String command = doc["command"].as<String>();
    JsonObject payload  = doc["payload"].as<JsonObject>();

    StaticJsonDocument<1024> respDoc;
    JsonObject response = respDoc.to<JsonObject>();
    handleCommand(command, payload, response);

    String respStr;
    serializeJson(respDoc, respStr);
    httpServer.send(200, "application/json", respStr);
}

// ---------------------------------------------------------------------------
// WiFi scan handler — GET /api/wifi/scan
// ---------------------------------------------------------------------------
static void onWifiScan() {
    int n = WiFi.scanNetworks();
    StaticJsonDocument<4096> doc;
    JsonArray nets = doc.createNestedArray("networks");
    for (int i = 0; i < n; i++) {
        JsonObject net = nets.createNestedObject();
        net["ssid"]    = WiFi.SSID(i);
        net["rssi"]    = WiFi.RSSI(i);
        net["channel"] = WiFi.channel(i);
        net["bssid"]   = WiFi.BSSIDstr(i);
    }
    String out;
    serializeJson(doc, out);
    httpServer.send(200, "application/json", out);
}

// ---------------------------------------------------------------------------
// RSSI endpoint — GET /api/rssi
// ---------------------------------------------------------------------------
static void onGetRssi() {
    StaticJsonDocument<64> doc;
    doc["rssi"] = WiFi.RSSI();
    String out;
    serializeJson(doc, out);
    httpServer.send(200, "application/json", out);
}

// ---------------------------------------------------------------------------
// WiFi connection helper
// ---------------------------------------------------------------------------
static bool connectWifi(const char* ssid, const char* password) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    Serial.printf("[WiFi] Connecting to %s", ssid);
    uint8_t attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());
        return true;
    }
    Serial.println("[WiFi] Connection failed");
    return false;
}

// ---------------------------------------------------------------------------
// OTA update
// ---------------------------------------------------------------------------
static void performOTA(const String& url, JsonObject& response) {
    WiFiClient client;
    t_httpUpdate_return ret = httpUpdate.update(client, url);
    switch (ret) {
        case HTTP_UPDATE_OK:
            response["status"]  = "ok";
            response["message"] = "OTA success — rebooting";
            ESP.restart();
            break;
        case HTTP_UPDATE_FAILED:
            response["status"]  = "failed";
            response["error"]   = httpUpdate.getLastErrorString();
            break;
        case HTTP_UPDATE_NO_UPDATES:
            response["status"]  = "no_update";
            break;
    }
}

// ---------------------------------------------------------------------------
// Feature module setup — called from base setup()
// ---------------------------------------------------------------------------
void __attribute__((constructor)) wifiFeatureSetup() {
    // Attempt connection with compile-time credentials
    if (strlen(WIFI_SSID) > 0) {
        wifiConnected = connectWifi(WIFI_SSID, WIFI_PASSWORD);
    }

    if (wifiConnected) {
        if (MDNS.begin(DEVICE_NAME)) {
            MDNS.addService("http", "tcp", API_PORT);
            Serial.printf("[mDNS] Registered as %s.local\n", DEVICE_NAME);
        }
    }

    // Register HTTP routes
    httpServer.on("/api/command", HTTP_POST, onApiCommand);
    httpServer.on("/api/wifi/scan", HTTP_GET, onWifiScan);
    httpServer.on("/api/rssi", HTTP_GET, onGetRssi);
    httpServer.begin();
    Serial.printf("[HTTP] Server listening on port %d\n", API_PORT);
}

// ---------------------------------------------------------------------------
// Feature module loop hook (called from main loop())
// ---------------------------------------------------------------------------
void wifiFeatureLoop() {
    httpServer.handleClient();
}
