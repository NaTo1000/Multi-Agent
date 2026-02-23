/**
 * ESP32 Multi-Agent Base Firmware
 *
 * Provides the core HTTP command server that the orchestrator communicates
 * with.  Feature modules (wifi.cpp, ble.cpp, gps.cpp) are appended by the
 * FirmwareAgent at build time.
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>

// ---------------------------------------------------------------------------
// Configuration (injected at build time by FirmwareAgent)
// ---------------------------------------------------------------------------
#ifndef FIRMWARE_VERSION
  #define FIRMWARE_VERSION "1.0.0"
#endif
#ifndef DEVICE_NAME
  #define DEVICE_NAME "ESP32-MultiAgent"
#endif
#ifndef API_PORT
  #define API_PORT 80
#endif
#ifndef OTA_ENABLED
  #define OTA_ENABLED 1
#endif

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
Preferences prefs;
float g_frequency_hz = 2400000000.0f;
String g_modulation   = "GFSK";
uint32_t g_boot_time  = 0;

// ---------------------------------------------------------------------------
// Forward declarations
// ---------------------------------------------------------------------------
void handleCommand(const String& command, const JsonObject& payload,
                   JsonObject& response);
void otaUpdate(const String& url, JsonObject& response);

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    g_boot_time = millis();

    prefs.begin("multiagent", false);
    g_frequency_hz = prefs.getFloat("freq_hz", 2400000000.0f);
    g_modulation   = prefs.getString("modulation", "GFSK");

    Serial.printf("[BOOT] ESP32 Multi-Agent v%s — %s\n",
                  FIRMWARE_VERSION, DEVICE_NAME);

#if OTA_ENABLED
    // OTA and WiFi initialised by wifi.cpp feature module
#endif
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------
void loop() {
    // Feature modules inject their own loop handlers via function hooks.
    // The HTTP server is non-blocking (handled in wifi.cpp).
    delay(10);
}

// ---------------------------------------------------------------------------
// Command dispatcher — called by the HTTP server in wifi.cpp
// ---------------------------------------------------------------------------
void handleCommand(const String& command, const JsonObject& payload,
                   JsonObject& response) {

    if (command == "get_status") {
        response["status"]           = "ok";
        response["firmware_version"] = FIRMWARE_VERSION;
        response["device_name"]      = DEVICE_NAME;
        response["uptime_ms"]        = millis() - g_boot_time;

    } else if (command == "set_frequency") {
        g_frequency_hz = payload["frequency_hz"].as<float>();
        prefs.putFloat("freq_hz", g_frequency_hz);
        response["status"]       = "ok";
        response["frequency_hz"] = g_frequency_hz;

    } else if (command == "get_frequency") {
        response["status"]       = "ok";
        response["frequency_hz"] = g_frequency_hz;

    } else if (command == "set_modulation") {
        g_modulation = payload["scheme"].as<String>();
        prefs.putString("modulation", g_modulation);
        response["status"]    = "ok";
        response["modulation"] = g_modulation;

    } else if (command == "get_rssi") {
        // RSSI reading is provided by wifi.cpp; fallback shown here.
        response["status"] = "ok";
        response["rssi"]   = -70;   // placeholder

    } else if (command == "get_firmware_info") {
        response["status"]     = "ok";
        response["version"]    = FIRMWARE_VERSION;
        response["build_date"] = __DATE__;

    } else if (command == "diagnostics") {
        response["status"]          = "ok";
        response["uptime_sec"]      = (millis() - g_boot_time) / 1000;
        response["free_heap_bytes"] = ESP.getFreeHeap();
        response["cpu_freq_mhz"]    = ESP.getCpuFreqMHz();

    } else if (command == "ota_update") {
        otaUpdate(payload["url"].as<String>(), response);

    } else if (command == "ota_rollback") {
        // Requires esp_ota_ops — implemented when OTA_ENABLED
        response["status"] = "not_supported";

    } else {
        response["status"] = "unknown_command";
        response["command"] = command;
    }
}

// ---------------------------------------------------------------------------
// OTA update stub — full implementation in wifi.cpp
// ---------------------------------------------------------------------------
void otaUpdate(const String& url, JsonObject& response) {
#if OTA_ENABLED
    // Delegated to wifi.cpp HTTPUpdate handler
    response["status"] = "initiated";
    response["url"]    = url;
#else
    response["status"] = "ota_disabled";
#endif
}
