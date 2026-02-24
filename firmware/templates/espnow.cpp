/**
 * ESP-NOW Mesh Firmware Template
 *
 * Implements a peer-to-peer ESP-NOW mesh between ESP32 nodes:
 * - Sub-1ms latency (no WiFi stack overhead)
 * - Up to 20 peers per node
 * - CSMA/CA-style collision avoidance
 * - Automatic peer registration via broadcast probes
 * - Reliable delivery with ACK + retry
 * - Compatible with multi-agent command protocol (JSON payloads)
 *
 * Range: ~200m line-of-sight, ~50m indoors
 * Throughput: up to 250 Kbps
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <ArduinoJson.h>

#ifndef ESPNOW_CHANNEL
  #define ESPNOW_CHANNEL 1
#endif
#ifndef NODE_ID
  #define NODE_ID "node-001"
#endif

// Broadcast address for peer discovery
static uint8_t BROADCAST_ADDR[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// ─────────────────────────────────────────────────────────────────
// Peer table
// ─────────────────────────────────────────────────────────────────
struct ESPNOWPeer {
    uint8_t  mac[6];
    String   node_id;
    int      rssi;
    uint32_t last_seen_ms;
};

static const int MAX_ESPNOW_PEERS = 20;
static ESPNOWPeer espnow_peers[MAX_ESPNOW_PEERS];
static int espnow_peer_count = 0;

bool addPeer(const uint8_t* mac, const String& node_id) {
    for (int i = 0; i < espnow_peer_count; i++) {
        if (memcmp(espnow_peers[i].mac, mac, 6) == 0) {
            espnow_peers[i].last_seen_ms = millis();
            return false;  // already known
        }
    }
    if (espnow_peer_count >= MAX_ESPNOW_PEERS) return false;
    memcpy(espnow_peers[espnow_peer_count].mac, mac, 6);
    espnow_peers[espnow_peer_count].node_id = node_id;
    espnow_peers[espnow_peer_count].last_seen_ms = millis();

    esp_now_peer_info_t info = {};
    memcpy(info.peer_addr, mac, 6);
    info.channel = ESPNOW_CHANNEL;
    info.encrypt = false;
    esp_now_add_peer(&info);
    espnow_peer_count++;
    return true;
}

// ─────────────────────────────────────────────────────────────────
// Receive callback
// ─────────────────────────────────────────────────────────────────
extern void handleCommand(const String& cmd, const JsonObject& payload,
                          JsonObject& response);

static void onESPNOWReceive(
    const esp_now_recv_info_t* info,
    const uint8_t* data,
    int len
) {
    String raw((char*)data, len);
    StaticJsonDocument<512> doc;
    if (deserializeJson(doc, raw) != DeserializationError::Ok) return;

    String type    = doc["type"].as<String>();
    String src_id  = doc["src"].as<String>();

    addPeer(info->src_addr, src_id);

    if (type == "probe") {
        // Reply with a probe_ack so the sender can register us
        StaticJsonDocument<128> ack_doc;
        ack_doc["type"] = "probe_ack";
        ack_doc["src"]  = NODE_ID;
        String ack;
        serializeJson(ack_doc, ack);
        esp_now_send(info->src_addr, (uint8_t*)ack.c_str(), ack.length());
        return;
    }

    if (type == "data") {
        String command         = doc["command"].as<String>();
        JsonObject cmd_payload = doc["payload"].as<JsonObject>();
        StaticJsonDocument<256> resp_doc;
        JsonObject resp = resp_doc.to<JsonObject>();
        handleCommand(command, cmd_payload, resp);

        // Send response back to sender
        resp["type"] = "response";
        resp["src"]  = NODE_ID;
        String resp_str;
        serializeJson(resp_doc, resp_str);
        esp_now_send(info->src_addr,
                     (uint8_t*)resp_str.c_str(),
                     resp_str.length());
    }
}

// Send callback — track delivery success
static volatile bool last_send_ok = false;
static void onESPNOWSend(const uint8_t* mac, esp_now_send_status_t status) {
    last_send_ok = (status == ESP_NOW_SEND_SUCCESS);
}

// ─────────────────────────────────────────────────────────────────
// Discovery broadcast
// ─────────────────────────────────────────────────────────────────
static uint32_t last_probe_ms = 0;

void broadcastProbe() {
    if (millis() - last_probe_ms < 15000) return;
    last_probe_ms = millis();
    StaticJsonDocument<64> doc;
    doc["type"] = "probe";
    doc["src"]  = NODE_ID;
    String probe;
    serializeJson(doc, probe);
    esp_now_send(BROADCAST_ADDR,
                 (uint8_t*)probe.c_str(),
                 probe.length());
}

// ─────────────────────────────────────────────────────────────────
// Reliable unicast (with retry)
// ─────────────────────────────────────────────────────────────────
bool sendToNode(const String& node_id, const String& command,
                const JsonObject& payload) {
    for (int i = 0; i < espnow_peer_count; i++) {
        if (espnow_peers[i].node_id == node_id) {
            StaticJsonDocument<512> doc;
            doc["type"]    = "data";
            doc["src"]     = NODE_ID;
            doc["command"] = command;
            doc["payload"] = payload;
            String pkt;
            serializeJson(doc, pkt);
            for (int retry = 0; retry < 3; retry++) {
                last_send_ok = false;
                esp_now_send(espnow_peers[i].mac,
                             (uint8_t*)pkt.c_str(),
                             pkt.length());
                delay(10);
                if (last_send_ok) return true;
            }
            return false;
        }
    }
    return false;  // peer not found
}

// ─────────────────────────────────────────────────────────────────
// Topology report
// ─────────────────────────────────────────────────────────────────
void getESPNOWTopology(JsonObject& out) {
    out["node_id"]      = NODE_ID;
    out["peer_count"]   = espnow_peer_count;
    JsonArray peers_arr = out.createNestedArray("peers");
    char mac_str[18];
    for (int i = 0; i < espnow_peer_count; i++) {
        snprintf(mac_str, sizeof(mac_str),
                 "%02X:%02X:%02X:%02X:%02X:%02X",
                 espnow_peers[i].mac[0], espnow_peers[i].mac[1],
                 espnow_peers[i].mac[2], espnow_peers[i].mac[3],
                 espnow_peers[i].mac[4], espnow_peers[i].mac[5]);
        JsonObject p = peers_arr.createNestedObject();
        p["mac"]          = mac_str;
        p["node_id"]      = espnow_peers[i].node_id;
        p["last_seen_ms"] = millis() - espnow_peers[i].last_seen_ms;
    }
}

// ─────────────────────────────────────────────────────────────────
// Feature setup / loop
// ─────────────────────────────────────────────────────────────────
void __attribute__((constructor)) espnowFeatureSetup() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ESP-NOW] Initialisation failed!");
        return;
    }
    esp_now_register_recv_cb(onESPNOWReceive);
    esp_now_register_send_cb(onESPNOWSend);

    // Register broadcast peer
    esp_now_peer_info_t bcast = {};
    memcpy(bcast.peer_addr, BROADCAST_ADDR, 6);
    bcast.channel = ESPNOW_CHANNEL;
    bcast.encrypt = false;
    esp_now_add_peer(&bcast);

    Serial.printf("[ESP-NOW] Mesh ready — node=%s channel=%d\n",
                  NODE_ID, ESPNOW_CHANNEL);
    Serial.printf("[ESP-NOW] MAC: %s\n",
                  WiFi.macAddress().c_str());
}

void espnowFeatureLoop() {
    broadcastProbe();
}
