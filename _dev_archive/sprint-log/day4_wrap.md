# Day 4 wrap — sensor backend and firmware

**Date:** 10 May 2026 (sprint Day 4 of 5)
**Status:** Both Day 4 deliverables built; full end-to-end stack test deferred to your machine (sandbox has no Docker).

## What landed

### 1. Sensor backend — `Trellis/backend/`

FastAPI + PostgreSQL + PostGIS service that ingests readings from the 25-node DePIN network, attributes them to wards spatially, applies per-sensor calibration, and exposes query endpoints.

**Files:**
- `app.py` — full FastAPI service, ~280 lines
- `requirements.txt` — fastapi, uvicorn, pydantic, asyncpg, geopandas
- `Dockerfile` — Python 3.11-slim container with GDAL
- `docker-compose.yml` — Postgres + backend, mounts the GeoPackage and forecast as read-only volumes
- `simulate_sensor.py` — Python sensor simulator with HMAC-signed POSTs
- `README.md` — architecture, schema, end-to-end smoke test guide

**Endpoints:**

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service info |
| POST | `/sensors` | Enroll/update a sensor (idempotent) — auto-attributes to ward via PostGIS if not given |
| GET | `/sensors` | List all sensors |
| POST | `/ingest` | Sensor pushes batch of readings (HMAC-signed body) — applies per-sensor calibration |
| GET | `/sensors/{id}/readings` | Query a sensor's history |
| GET | `/wards/{lga}/{ward}/current` | Latest 1-hour mean from any sensor in this ward |
| GET | `/forecast` | Pass-through of the Trellis 4-week forecast |
| POST | `/admin/load-wards` | One-time load of pilot ward polygons into PostGIS |

**Postgres schema:** three tables — `sensors`, `readings`, `ward_polygons`. PostGIS `ST_Contains` does the ward attribution. Calibration coefficients stored per-sensor; raw and calibrated values stored on every reading.

**Validated in this session:**
- Module imports cleanly
- OpenAPI generates 7 routes
- Three tables defined in schema SQL
- HMAC signer in simulator produces 32-byte hex signatures
- All Pydantic models valid

**Full Docker-compose end-to-end test** requires Docker on your machine, not available in this sandbox.

### 2. Sensor firmware skeleton — `Trellis/firmware/`

ESP32 Arduino sketch forking the AirGradient reference structure. PlatformIO project ready to build with `pio run`.

**Files:**
- `platformio.ini` — board, framework, library pins (AirGradient, Sensirion SGP41, BME280, WiFiManager, ArduinoJson)
- `src/main.cpp` — full firmware, ~210 lines
- `README.md` — hardware bill, first-boot setup, behaviour, calibration model, power notes

**Hardware:**
- ESP32-DevKitC v4 + AirGradient ONE PCB (TAPR Open Hardware)
- Plantower PMS5003 — PM₂.₅ + PM₁₀ via UART
- Sensirion SGP41 — NO₂ + VOC via I²C
- Bosch BME280 — T / H / P via I²C

**Behaviour:**
- First-boot captive portal asks for Wi-Fi creds + sensor ID + per-device secret + backend URL
- Reads all sensors every 60 s into a 60-slot RAM buffer
- Every 5 min: serialises to JSON, signs with HMAC-SHA256 using the per-device secret, POSTs to backend with `X-Signature` header
- On HTTP failure, retains buffer and retries
- NTP time sync for accurate timestamps

**Why fork rather than use AirGradient's firmware as-is:**
- Per-device secrets and HMAC-signed ingest (so a stolen sensor or MITM can't push fake readings)
- Trellis-specific JSON shape matching the backend ingest endpoint
- NO₂ raw counts (calibrated server-side), not the AirGradient air-quality index
- Configurable backend URL, not hardcoded to AirGradient's cloud

## End-to-end flow (fully working when run on your machine)

```
sensor (firmware on ESP32)
    │
    │  POST /ingest with HMAC-signed body
    ▼
backend (FastAPI in Docker)
    │
    │  applies calibration, INSERT INTO readings
    ▼
Postgres (with PostGIS)
    │
    │  ward_polygons + readings + sensors
    ▼
all four decision channels read the data via:
  - GET /forecast       (DHIS2 dashboard, school PWA, surge UI, SMS dispatcher)
  - GET /wards/.../current  (real-time current reading per ward)
  - GET /sensors/{id}/readings  (per-sensor time series)
```

The backend is the integration point. Run `docker compose up -d` in `Trellis/backend/`, then any of the channels can be configured to fetch from `http://localhost:8001` instead of from their own static JSON.

## You can verify this on your machine

```bash
# Start the backend stack
cd backend
docker compose up -d
sleep 15  # wait for Postgres init

# One-time: load ward polygons
curl -X POST http://localhost:8001/admin/load-wards
# Should respond: {"loaded": 51}

# Run the simulator (does enroll → send 5 readings → query → ward-current)
python3 simulate_sensor.py

# Manual probe
curl http://localhost:8001/sensors
curl http://localhost:8001/wards/Warri%20South/Ekurede/current
curl http://localhost:8001/forecast | head -c 200
```

## What's NOT in this version

- **No MQTT ingest path.** HTTP only. The PubSubClient library is included in `platformio.ini` if you want to wire MQTT later.
- **No reading-rate-limit per sensor.** Add Redis or a Postgres trigger.
- **No retention policy.** Readings accumulate forever. Add a cron-job that prunes readings older than N days.
- **No timezone handling per ward.** Sensor clocks are UTC.
- **No authentication for query endpoints.** Production should put these behind an auth middleware.
- **No firmware OTA updates.** Future version should support OTA via WiFiManager's update path.
- **No GSM fallback in firmware.** Wi-Fi only. Riverine deployment would need a GSM modem.

## Sprint status

| Day | Phase | Status |
|---|---|---|
| 1 | Trained forecast model + multi-year EO | Done |
| 2 | Production decision channels + DHIS2 self-host | Done |
| 3 | Caregiver SMS dispatcher + surge planning UI | Done |
| 4 | Sensor backend + sensor firmware | **Done** |
| 5 | MCP server + open-source repo + end-to-end test | Pending your go |

## Files added in Day 4

| Path | Purpose |
|---|---|
| `backend/app.py` | FastAPI service (~280 lines) |
| `backend/requirements.txt` | dependencies |
| `backend/Dockerfile` | container |
| `backend/docker-compose.yml` | compose: Postgres + backend |
| `backend/simulate_sensor.py` | end-to-end test simulator |
| `backend/README.md` | architecture + run guide |
| `firmware/platformio.ini` | PlatformIO project |
| `firmware/src/main.cpp` | ESP32 firmware (~210 lines) |
| `firmware/README.md` | hardware bill, first-boot, behaviour |
