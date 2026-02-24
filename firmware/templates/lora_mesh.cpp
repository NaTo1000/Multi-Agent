/**
 * LoRa Mesh Firmware Template
 *
 * Implements a self-healing LoRa mesh network across ESP32 nodes:
 * - Every node can be both a gateway and a relay
 * - Flooding-based multi-hop routing with hop-count limiting
 * - RSSI-based neighbour table maintenance
 * - Automatic mesh topology reporting to the orchestrator
 * - Compatible with SX1276 / SX1278 (HopeRF RFM95) modules via SPI
 *
 * Required library: LoRa by Sandeep Mistry
 * Hardware: LoRa module on SPI (MOSI=23, MISO=19, SCK=18, NSS=5, RST=14, DIO0=26)
 */

#include <Arduino.h>
#include <LoRa.h>
#include <ArduinoJson.h>

#ifndef LORA_FREQ
  #define LORA_FREQ      915E6    // 915 MHz Americas / 868 MHz Europe
#endif
#ifndef LORA_SF
  #define LORA_SF        9        // Spreading factor (7-12)
#endif
#ifndef LORA_BW
  #define LORA_BW        125E3    // Bandwidth Hz
#endif
#ifndef LORA_CR
  #define LORA_CR        5        // Coding rate denominator (5=4/5 … 8=4/8)
#endif
#ifndef LORA_TX_POWER
  #define LORA_TX_POWER  14       // dBm (2–20)
#endif
#ifndef MESH_TTL
  #define MESH_TTL       5        // Max hops before packet is discarded
#endif
#ifndef NODE_ID
  #define NODE_ID        "node-001"
#endif

// SPI pins
static const int LORA_NSS  = 5;
static const int LORA_RST  = 14;
static const int LORA_DIO0 = 26;

// ─────────────────────────────────────────────────────────────────
// Neighbour table
// ─────────────────────────────────────────────────────────────────
struct Neighbour {
    String  node_id;
    int     rssi;
    uint32_t last_seen_ms;
};

static const int MAX_NEIGHBOURS = 10;
static Neighbour neighbours[MAX_NEIGHBOURS];
static int neighbour_count = 0;

void updateNeighbour(const String& nid, int rssi) {
    for (int i = 0; i < neighbour_count; i++) {
        if (neighbours[i].node_id == nid) {
            neighbours[i].rssi = rssi;
            neighbours[i].last_seen_ms = millis();
            return;
        }
    }
    if (neighbour_count < MAX_NEIGHBOURS) {
        neighbours[neighbour_count++] = {nid, rssi, millis()};
    }
}

// ─────────────────────────────────────────────────────────────────
// Seen-packet dedup cache (prevent relay loops)
// ─────────────────────────────────────────────────────────────────
static const int SEEN_CACHE_SIZE = 32;
static uint32_t seen_ids[SEEN_CACHE_SIZE];
static int seen_head = 0;

bool alreadySeen(uint32_t pkt_id) {
    for (int i = 0; i < SEEN_CACHE_SIZE; i++) {
        if (seen_ids[i] == pkt_id) return true;
    }
    return false;
}

void markSeen(uint32_t pkt_id) {
    seen_ids[seen_head % SEEN_CACHE_SIZE] = pkt_id;
    seen_head++;
}

// ─────────────────────────────────────────────────────────────────
// Packet structure
// ─────────────────────────────────────────────────────────────────
// { "id": <uint32>, "src": "node-id", "dst": "*", "ttl": 5,
//   "type": "data|ack|beacon", "payload": {} }

void sendPacket(const String& type, const JsonObject& payload,
                const String& dst = "*") {
    static uint32_t seq = 0;
    StaticJsonDocument<512> doc;
    doc["id"]   = seq++;
    doc["src"]  = NODE_ID;
    doc["dst"]  = dst;
    doc["ttl"]  = MESH_TTL;
    doc["type"] = type;
    doc["payload"] = payload;

    String pkt;
    serializeJson(doc, pkt);
    LoRa.beginPacket();
    LoRa.print(pkt);
    LoRa.endPacket();
}

// ─────────────────────────────────────────────────────────────────
// Receive and relay
// ─────────────────────────────────────────────────────────────────
extern void handleCommand(const String& cmd, const JsonObject& payload,
                          JsonObject& response);  // from base.cpp

void processLoRaPacket() {
    int pkt_size = LoRa.parsePacket();
    if (pkt_size == 0) return;

    String raw;
    while (LoRa.available()) raw += (char)LoRa.read();
    int rssi = LoRa.packetRssi();

    StaticJsonDocument<512> doc;
    if (deserializeJson(doc, raw) != DeserializationError::Ok) return;

    uint32_t pkt_id = doc["id"].as<uint32_t>();
    if (alreadySeen(pkt_id)) return;
    markSeen(pkt_id);

    String src  = doc["src"].as<String>();
    String dst  = doc["dst"].as<String>();
    String type = doc["type"].as<String>();
    int ttl     = doc["ttl"].as<int>() - 1;

    updateNeighbour(src, rssi);

    if (type == "beacon") {
        // Just update neighbour table
        return;
    }

    if (dst == "*" || dst == NODE_ID) {
        // This packet is for us — dispatch to command handler
        if (type == "data") {
            JsonObject payload = doc["payload"].as<JsonObject>();
            String command = payload["command"].as<String>();
            JsonObject cmd_payload = payload["payload"].as<JsonObject>();
            StaticJsonDocument<512> resp_doc;
            JsonObject resp = resp_doc.to<JsonObject>();
            handleCommand(command, cmd_payload, resp);
            // Send ACK back to source
            StaticJsonDocument<128> ack_payload_doc;
            JsonObject ack_payload = ack_payload_doc.to<JsonObject>();
            ack_payload["ack_id"] = pkt_id;
            sendPacket("ack", ack_payload, src);
        }
    }

    // Relay if TTL remaining and it's a broadcast
    if (ttl > 0 && dst == "*") {
        doc["ttl"] = ttl;
        String relayed;
        serializeJson(doc, relayed);
        delay(random(10, 50));  // Random backoff to avoid collision
        LoRa.beginPacket();
        LoRa.print(relayed);
        LoRa.endPacket();
    }
}

// ─────────────────────────────────────────────────────────────────
// Beacon broadcast
// ─────────────────────────────────────────────────────────────────
static uint32_t last_beacon_ms = 0;
static const uint32_t BEACON_INTERVAL_MS = 30000;

void broadcastBeacon() {
    if (millis() - last_beacon_ms < BEACON_INTERVAL_MS) return;
    last_beacon_ms = millis();
    StaticJsonDocument<128> pay;
    JsonObject p = pay.to<JsonObject>();
    p["node_id"] = NODE_ID;
    p["uptime_ms"] = millis();
    sendPacket("beacon", p);
}

// ─────────────────────────────────────────────────────────────────
// Topology report endpoint (called via HTTP command handler)
// ─────────────────────────────────────────────────────────────────
void getMeshTopology(JsonObject& out) {
    out["node_id"]   = NODE_ID;
    out["neighbour_count"] = neighbour_count;
    JsonArray nbrs = out.createNestedArray("neighbours");
    for (int i = 0; i < neighbour_count; i++) {
        JsonObject n = nbrs.createNestedObject();
        n["node_id"]      = neighbours[i].node_id;
        n["rssi"]         = neighbours[i].rssi;
        n["last_seen_ms"] = millis() - neighbours[i].last_seen_ms;
    }
}

// ─────────────────────────────────────────────────────────────────
// Feature setup / loop
// ─────────────────────────────────────────────────────────────────
void __attribute__((constructor)) loraFeatureSetup() {
    LoRa.setPins(LORA_NSS, LORA_RST, LORA_DIO0);
    if (!LoRa.begin(LORA_FREQ)) {
        Serial.println("[LoRa] Initialisation failed!");
        return;
    }
    LoRa.setSpreadingFactor(LORA_SF);
    LoRa.setSignalBandwidth(LORA_BW);
    LoRa.setCodingRate4(LORA_CR);
    LoRa.setTxPower(LORA_TX_POWER);
    Serial.printf("[LoRa] Mesh ready — node=%s freq=%.0fMHz SF=%d\n",
                  NODE_ID, LORA_FREQ / 1e6, LORA_SF);
}

void loraFeatureLoop() {
    processLoRaPacket();
    broadcastBeacon();
}
