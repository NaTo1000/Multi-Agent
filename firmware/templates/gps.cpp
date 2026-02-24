/**
 * GPS / GNSS Feature Module
 *
 * Parses NMEA 0183 sentences from a serial GPS module connected to
 * the ESP32 UART2 (pins 16/17 by default).
 *
 * Exposes location data via the orchestrator command API and BLE TX.
 *
 * Requires TinyGPS++ library.
 */

#include <HardwareSerial.h>
#include <TinyGPS++.h>
#include <ArduinoJson.h>

#ifndef GPS_RX_PIN
  #define GPS_RX_PIN 16
#endif
#ifndef GPS_TX_PIN
  #define GPS_TX_PIN 17
#endif
#ifndef GPS_BAUD
  #define GPS_BAUD 9600
#endif

static TinyGPSPlus gps;
static HardwareSerial gpsSerial(2);

// ---------------------------------------------------------------------------
// GPS loop hook — call from main loop()
// ---------------------------------------------------------------------------
void gpsFeatureLoop() {
    while (gpsSerial.available() > 0) {
        gps.encode(gpsSerial.read());
    }
}

// ---------------------------------------------------------------------------
// Return current GPS fix as JSON
// ---------------------------------------------------------------------------
void getGpsJson(JsonObject& out) {
    out["fix"]        = gps.location.isValid();
    out["latitude"]   = gps.location.isValid() ? gps.location.lat() : 0.0;
    out["longitude"]  = gps.location.isValid() ? gps.location.lng() : 0.0;
    out["altitude_m"] = gps.altitude.isValid()  ? gps.altitude.meters() : 0.0;
    out["satellites"] = gps.satellites.isValid() ? gps.satellites.value() : 0;
    out["hdop"]       = gps.hdop.isValid()       ? gps.hdop.hdop() : 99.99;
    char ts[25];
    if (gps.date.isValid() && gps.time.isValid()) {
        snprintf(ts, sizeof(ts), "%04d-%02d-%02dT%02d:%02d:%02dZ",
                 gps.date.year(), gps.date.month(), gps.date.day(),
                 gps.time.hour(), gps.time.minute(), gps.time.second());
        out["timestamp"] = ts;
    }
}

// ---------------------------------------------------------------------------
// GPS feature setup
// ---------------------------------------------------------------------------
void __attribute__((constructor)) gpsFeatureSetup() {
    gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    Serial.printf("[GPS] UART2 rx=%d tx=%d baud=%d\n",
                  GPS_RX_PIN, GPS_TX_PIN, GPS_BAUD);
}
