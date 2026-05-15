# Trellis sensor node firmware

ESP32 firmware for the Trellis 25-node DePIN sensor network. Forks the AirGradient reference firmware structure and adds the Trellis-specific ingest path (HMAC-signed HTTP POST to the Trellis backend) plus a per-device secret.

## Hardware

The reference build uses:

| Component | Function | Interface |
|---|---|---|
| ESP32-DevKitC v4 | MCU + Wi-Fi | — |
| Plantower PMS5003 | PM₂.₅ + PM₁₀ (laser scattering) | UART |
| Sensirion SGP41 | NO₂ + VOC (mox-based) | I²C |
| Bosch BME280 | Temperature, humidity, pressure | I²C |
| AirGradient ONE PCB | Power + USB + LEDs (TAPR Open Hardware) | — |
| (Optional) SD card | Offline reading buffer | SPI |

Total bill of materials: approximately $250 per node at one-off pricing; lot-sized procurement is expected to drop this to under $200.

## Build

```bash
cd firmware
pip install platformio
pio run                  # compile
pio run -t upload        # flash to a connected ESP32
pio device monitor       # serial console
```

`platformio.ini` pins the AirGradient Arduino library so the build reproduces.

## First-boot configuration

On first boot the firmware enters captive-portal mode. Connect any phone or laptop to the Wi-Fi SSID `trellis-setup` and visit `192.168.4.1`. The portal asks for:

- **Wi-Fi SSID and password** — the network the sensor will use in operation
- **Sensor ID** — e.g. `TR-06`. Should match the node ID in the Trellis sensor allocation table
- **Per-device secret** — a 32-character random string provisioned by Trellis at deployment
- **Backend URL** — must be set to your Trellis backend ingest endpoint, e.g. `http://your-backend.example/ingest` or `http://192.168.1.50:8001/ingest` for a local-network sensor

The sensor saves these to flash, joins Wi-Fi, syncs NTP, and starts reading.

## Behaviour

Every 60 seconds: read PM₂.₅, PM₁₀, NO₂, temperature, humidity, pressure. Append to a 60-slot RAM buffer.

Every 5 minutes: POST the buffer to the Trellis backend. The body is a JSON object signed with HMAC-SHA256 using the per-device secret; the signature goes in the `X-Signature` header. The backend verifies the signature against its stored hash and writes the readings to Postgres after applying calibration.

On HTTP failure, the firmware keeps the buffer and retries on the next cycle. If the buffer fills (60 readings = ~1 hour), the oldest reading is dropped to make room. With an SD card sidecar attached and the optional library uncommented, readings are flushed to disk instead and replayed when connectivity returns.

## Calibration

The firmware sends *raw* sensor values. Calibration coefficients live on the backend, in the `sensors` table. This means a calibration update is a server-side `UPDATE sensors SET cal_pm25_a = ...` — no firmware re-flash needed.

For deployed sensors, the deployment plan calls for a 4-week co-location with a NIST-traceable mobile reference instrument; the resulting linear regression coefficients become the sensor's calibration constants.

## Power

ESP32 idle: ~80 mA at 3.3 V. PMS5003 with fan: ~120 mA at 5 V. SGP41: 8 mA. BME280: 0.7 mA. Total: ~1 W average, peaking at ~2 W during PMS5003 startup.

For sites without mains, a 6 V 6 W solar panel + 18650 cell + LDO is sufficient. Sleep mode between reads (not enabled in this firmware) drops average draw below 200 mA.

## Why this firmware exists separate from AirGradient's

AirGradient's reference firmware is excellent for community air-quality monitoring with their MQTT or HTTP push to AirGradient's cloud. Trellis needs:

- **Per-device secrets and HMAC-signed ingest** — so a stolen sensor or a man-in-the-middle cannot push fake readings into the platform
- **Specific JSON shape** matching the Trellis backend ingest endpoint
- **NO₂ raw counts**, not the AirGradient-internal aggregated air quality index
- **HTTPS to a configurable backend URL**, not hardcoded to AirGradient's cloud

Everything else — the PMS5003 driver code, the BME280 wiring, the WiFiManager portal — is unchanged from AirGradient's published library. The Trellis-specific code is the bottom half of `src/main.cpp` below the `============ TRELLIS-SPECIFIC CODE` marker.

## What this firmware does NOT do (yet)

- **No OTA (over-the-air) updates.** A future version should support OTA via WiFiManager's update path.
- **No SD-card buffer enabled by default.** Add the lib in `platformio.ini` and the buffer code is straightforward.
- **No MQTT publish.** Only HTTP POST. The PubSubClient library is included if you want to add MQTT.
- **No deep sleep.** Constant operation; battery-only deployment would need significant work.
- **No outbound fallback to GSM.** Wi-Fi only. Riverine deployment would need a GSM modem.
- **No physical button to enter setup mode.** Re-flashing is the only way to redo Wi-Fi setup.

## Open hardware commitment

This firmware ships under the same TAPR Open Hardware License as the AirGradient base. Any other Niger Delta state, or any other oil-bearing region facing the same exposure-and-coverage problem, can re-build the network from these files.
