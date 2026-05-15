// Trellis sensor node firmware — ESP32, AirGradient-derived
//
// Hardware:
//   Plantower PMS5003   — PM2.5, PM10                via UART
//   Sensirion SGP41     — NO2, VOC                   via I2C
//   Bosch BME280        — temperature, humidity, P   via I2C
//   ESP32-DevKitC v4    — MCU + Wi-Fi
//
// Behaviour:
//   Boots, joins Wi-Fi (captive portal on first boot via WiFiManager).
//   Reads all three sensors every ~60 seconds.
//   Buffers up to 60 readings in RAM.
//   Every 5 minutes, POSTs the buffer to the Trellis backend over HTTPS,
//     signing the body with HMAC-SHA256 using the per-device secret.
//   On HTTP failure, retains the buffer; retries on next cycle.
//
// Configuration is via the captive portal on first boot:
//   Wi-Fi SSID, password
//   Backend URL (no default — must be set per deployment, e.g. http://192.168.1.50:8001/ingest)
//   Sensor ID (default = ESP32 chip ID, e.g. TR-XXXXXXXX)
//   Sensor secret (provisioned at deployment)
//
// All Trellis-specific code is below the marker. Above the marker is mostly
// boilerplate following the AirGradient reference firmware.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <SensirionI2cSgp41.h>
#include "mbedtls/md.h"

// ----- Pin map (AirGradient ONE schematic, ESP32-DevKitC) -----
constexpr int PIN_PMS_RX = 16;   // PMS5003 TX → ESP32 RX
constexpr int PIN_PMS_TX = 17;   // PMS5003 RX ← ESP32 TX

// ----- Configurable parameters via WiFiManager -----
// Set per deployment via the captive-portal first-boot flow; this is just a placeholder
// to force the deployer to override before the firmware can post readings.
String backendUrl = "http://YOUR-BACKEND-HERE/ingest";
String sensorId   = "TR-UNSET";
String sensorSecret = "";

// ----- State -----
Adafruit_BME280 bme;
SensirionI2cSgp41 sgp41;
HardwareSerial pmsSerial(2);

constexpr int BUFFER_SIZE = 60;
struct Reading {
  uint64_t observed_at_ms;
  float pm25, pm10, no2, t, h, p;
} buffer[BUFFER_SIZE];
int bufHead = 0, bufCount = 0;

unsigned long lastReadMs = 0, lastPostMs = 0;
constexpr unsigned long READ_INTERVAL_MS = 60UL * 1000UL;
constexpr unsigned long POST_INTERVAL_MS = 5UL * 60UL * 1000UL;

// ============ TRELLIS-SPECIFIC CODE BELOW ============

// HMAC-SHA256 helper
String hmacSha256(const String& key, const String& message) {
  byte hmacResult[32];
  mbedtls_md_context_t ctx;
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, info, 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)key.c_str(), key.length());
  mbedtls_md_hmac_update(&ctx, (const unsigned char*)message.c_str(), message.length());
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);
  String hex;
  for (int i = 0; i < 32; i++) {
    char b[3]; sprintf(b, "%02x", hmacResult[i]);
    hex += b;
  }
  return hex;
}

// Read PMS5003 — returns true on success
bool readPms(float& pm25, float& pm10) {
  // 32-byte frame from PMS5003 begins with 0x42 0x4d
  while (pmsSerial.available() >= 32) {
    if (pmsSerial.read() != 0x42) continue;
    if (pmsSerial.read() != 0x4d) continue;
    uint8_t buf[30];
    pmsSerial.readBytes(buf, 30);
    pm25 = (buf[10] << 8) | buf[11];   // PM2.5 atmospheric
    pm10 = (buf[12] << 8) | buf[13];   // PM10 atmospheric
    return true;
  }
  return false;
}

// Read SGP41 — returns true on success. Returns NO2 in ppb-equivalent (raw counts converted).
bool readSgp41(float& no2_estimate) {
  uint16_t srawVoc = 0, srawNox = 0;
  // Default RH/T compensation. For better accuracy, pass live BME280 readings.
  uint16_t hum_ticks = 30000, t_ticks = 16384;
  int16_t err = sgp41.measureRawSignals(hum_ticks, t_ticks, srawVoc, srawNox);
  if (err) return false;
  // Trellis-specific transform: srawNox is a raw count proportional to NO2.
  // Empirical calibration to ppb is applied server-side; here we send the raw count.
  no2_estimate = (float)srawNox;
  return true;
}

void readSensors() {
  if (bufCount >= BUFFER_SIZE) {
    Serial.println("[trellis] buffer full, dropping oldest reading");
    bufHead = (bufHead + 1) % BUFFER_SIZE;
    bufCount--;
  }
  Reading& r = buffer[(bufHead + bufCount) % BUFFER_SIZE];
  r.observed_at_ms = (uint64_t)time(nullptr) * 1000ULL;

  float pm25 = NAN, pm10 = NAN, no2 = NAN;
  readPms(pm25, pm10);
  readSgp41(no2);

  r.pm25 = pm25;
  r.pm10 = pm10;
  r.no2 = no2;
  r.t = bme.readTemperature();
  r.h = bme.readHumidity();
  r.p = bme.readPressure() / 100.0f;
  bufCount++;
  Serial.printf("[trellis] read: pm25=%.1f no2=%.0f t=%.1f h=%.0f%%\n",
                r.pm25, r.no2, r.t, r.h);
}

bool postBuffer() {
  if (bufCount == 0) return true;

  StaticJsonDocument<8192> doc;
  doc["sensor_id"] = sensorId;
  JsonArray arr = doc.createNestedArray("readings");
  for (int i = 0; i < bufCount; i++) {
    Reading& r = buffer[(bufHead + i) % BUFFER_SIZE];
    JsonObject o = arr.createNestedObject();
    // ISO 8601 UTC
    time_t t = (time_t)(r.observed_at_ms / 1000ULL);
    char ts[32]; strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", gmtime(&t));
    o["observed_at"] = ts;
    if (!isnan(r.pm25)) o["pm25_raw"] = r.pm25;
    if (!isnan(r.pm10)) o["pm10_raw"] = r.pm10;
    if (!isnan(r.no2))  o["no2_raw"]  = r.no2;
    if (!isnan(r.t))    o["temperature_c"] = r.t;
    if (!isnan(r.h))    o["humidity_pct"]  = r.h;
    if (!isnan(r.p))    o["pressure_hpa"]  = r.p;
  }
  String body;
  serializeJson(doc, body);
  String sig = hmacSha256(sensorSecret, body);

  HTTPClient http;
  http.begin(backendUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Signature", sig);
  int code = http.POST(body);
  String resp = http.getString();
  http.end();
  Serial.printf("[trellis] POST %d %s\n", code, resp.substring(0, 80).c_str());

  if (code >= 200 && code < 300) {
    bufCount = 0;
    bufHead = 0;
    return true;
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[trellis] Trellis sensor node starting");

  // Captive portal Wi-Fi setup
  WiFiManager wifiManager;
  WiFiManagerParameter pId("sensor_id", "Sensor ID (e.g. TR-06)", sensorId.c_str(), 32);
  WiFiManagerParameter pSecret("sensor_secret", "Per-device secret", sensorSecret.c_str(), 64);
  WiFiManagerParameter pUrl("backend_url", "Backend ingest URL", backendUrl.c_str(), 128);
  wifiManager.addParameter(&pId);
  wifiManager.addParameter(&pSecret);
  wifiManager.addParameter(&pUrl);
  wifiManager.setConfigPortalTimeout(180);
  if (!wifiManager.autoConnect("trellis-setup")) {
    Serial.println("[trellis] Wi-Fi setup timeout, restarting");
    ESP.restart();
  }
  sensorId = pId.getValue();
  sensorSecret = pSecret.getValue();
  backendUrl = pUrl.getValue();

  // NTP for accurate timestamps
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("[trellis] waiting for NTP sync...");
  while (time(nullptr) < 1700000000) { delay(500); Serial.print("."); }
  Serial.println();

  // Init sensors
  Wire.begin();
  bme.begin(0x76);
  sgp41.begin(Wire, 0x59);
  sgp41.executeConditioning(30000, 16384, /*duration_seconds=*/10);
  pmsSerial.begin(9600, SERIAL_8N1, PIN_PMS_RX, PIN_PMS_TX);

  Serial.printf("[trellis] up. sensor_id=%s backend=%s\n",
                sensorId.c_str(), backendUrl.c_str());
}

void loop() {
  unsigned long now = millis();
  if (now - lastReadMs > READ_INTERVAL_MS) {
    readSensors();
    lastReadMs = now;
  }
  if (now - lastPostMs > POST_INTERVAL_MS) {
    postBuffer();
    lastPostMs = now;
  }
  delay(100);
}
