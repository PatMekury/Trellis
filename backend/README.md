# Trellis sensor backend

FastAPI + PostgreSQL + PostGIS service that ingests sensor readings from the 25-node DePIN network, applies per-sensor calibration, attributes readings to wards via spatial lookup, and exposes query endpoints for the dashboard, surge UI, and forecast proxy.

## What it does

| Endpoint | Purpose |
|---|---|
| `GET /` | Service info |
| `POST /sensors` | Enroll or update a sensor (id, channel, lat/lon, per-device secret, calibration coefficients) |
| `GET /sensors` | List all sensors |
| `POST /ingest` | Sensor pushes a batch of readings (HMAC-signed) |
| `GET /sensors/{id}/readings` | Query a sensor's reading history |
| `GET /wards/{lga}/{ward}/current` | Latest 1-hour mean from any sensor in this ward |
| `GET /forecast` | Pass-through of the Trellis 4-week forecast (so all four decision channels can hit one backend) |
| `POST /admin/load-wards` | One-time load of pilot ward polygons from the GeoPackage into PostGIS for spatial attribution |

## Run it

```bash
cd backend
docker compose up -d --build         # brings up Postgres + the FastAPI service
# wait ~10 seconds for Postgres to become healthy
docker compose ps                     # both containers should show Up
```

Service runs at `http://localhost:8001`. OpenAPI docs at `http://localhost:8001/docs`.

> **One-time step required for ward attribution:** the `ward_polygons` table is created empty by the schema. Until you load it, every sensor enrollment will have `lganame=null` and `wardname=null`, and `/wards/{lga}/{ward}/current` will return "no readings in the last hour" even when readings have been ingested. Load it once:
>
> ```bash
> curl -X POST http://localhost:8001/admin/load-wards
> ```
>
> Or in PowerShell: `Invoke-RestMethod -Method Post -Uri "http://localhost:8001/admin/load-wards"`. Expected response: `{"loaded": 51}`. After this, the next sensor enrollment with a lat/lon will be attributed to the containing ward via PostGIS `ST_Contains`.

> **Don't run `uvicorn` directly on the host.** The Postgres container has no host-side port mapping — it's only reachable on the internal Docker network at `postgres:5432`. Running `uvicorn app:app` from your shell will fail with `ConnectionRefusedError`. The backend is designed to run inside Docker; both containers come up together with `docker compose up`.

## End-to-end smoke test with the simulator

```bash
cd backend
python3 simulate_sensor.py
```

That single command:

1. Enrols a synthetic sensor at Ekurede coordinates (Warri South), 5.5347 / 5.7639
2. Sends 5 minute-readings of PM₂.₅ / PM₁₀ / NO₂ / T / H / P, HMAC-signed
3. Queries the last 5 readings (showing both raw and calibrated values)
4. Queries the ward-current endpoint (showing the 1-hour-mean per ward)

Verifies: enrollment, calibration math, HMAC verification, ward attribution via PostGIS, ingest, query, and ward aggregation.

> **HMAC-secret-mismatch trap:** `simulate_sensor.py` hardcodes `SENSOR_SECRET = "dev-secret-tr06"` (line 23). If you previously enrolled TR-06 with a different secret, the simulator's HMAC signing will fail verification and `/ingest` will reject every batch with 401. Two clean fixes:
>
> 1. Re-enroll via the simulator: `python simulate_sensor.py --enroll` overwrites the existing TR-06 row with `dev-secret-tr06`.
> 2. Edit line 23 in `simulate_sensor.py` to match whatever secret you used at enrolment.

### Manual enrollment via PowerShell (Windows)

The PowerShell `curl` alias (which is `Invoke-WebRequest`) does not handle nested-quoted JSON cleanly. Use either of these instead:

```powershell
# Option 1: Invoke-RestMethod (PowerShell-native)
$body = @{sensor_id="TR-06"; channel="PHC"; latitude=5.5347; longitude=5.7639; secret="dev-secret-tr06"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8001/sensors" -ContentType "application/json" -Body $body

# Option 2: write the body to a file, use curl.exe --data @
'{"sensor_id":"TR-06","channel":"PHC","latitude":5.5347,"longitude":5.7639,"secret":"dev-secret-tr06"}' | Out-File body.json -Encoding utf8
curl.exe -X POST "http://localhost:8001/sensors" -H "Content-Type: application/json" --data "@body.json"
```

The `curl.exe` form (note the `.exe`) bypasses the PowerShell alias and uses the real curl binary that ships with Windows 10+.

## Calibration

Each sensor has four calibration coefficients stored in the `sensors` table:

- `cal_pm25_a`, `cal_pm25_b` — applied as `pm25 = a × pm25_raw + b`
- `cal_no2_a`, `cal_no2_b` — applied as `no2 = a × no2_raw + b`

These are determined per-sensor at deployment by 4-week co-location with a NIST-traceable reference instrument. The backend stores both `pm25_raw` and `pm25` (calibrated) on every reading so the calibration can be retrospectively re-applied if coefficients change.

## Authentication

Each sensor has a per-device secret (provisioned at enrolment, never leaves the firmware). The secret hash is stored server-side. Each `POST /ingest` request signs the JSON body with HMAC-SHA256 using the secret; the signature goes in the `X-Signature` header.

For development, set `TRELLIS_SKIP_HMAC=1` in the docker-compose env to bypass signature verification. The simulator does sign its requests properly so you can test the auth path with `TRELLIS_SKIP_HMAC=0`.

## Ward attribution via PostGIS

When a sensor is enrolled with a lat/lon but no `lganame` / `wardname`, the backend runs a PostGIS `ST_Contains` lookup against the loaded `ward_polygons` table to attribute the sensor automatically. This means firmware just needs to know its GPS coordinates; the backend figures out the ward.

## Forecast proxy

Once the backend is running, all four decision channels can be configured to fetch the forecast from `http://backend:8001/forecast` instead of bundling their own JSON. This means a single update to the forecast file refreshes every channel automatically.

To wire up: change the `fetch("forecast.json")` call in each channel's HTML/JS to `fetch("http://localhost:8001/forecast")`. Or run them all behind a reverse proxy that maps `/forecast` to the backend.

## Schema

```sql
sensors
  id              TEXT PRIMARY KEY            -- e.g. TR-06
  channel         TEXT                         -- 'PHC' | 'school' | 'community'
  lganame, wardname  TEXT                      -- attributed by PostGIS or set on enrol
  latitude, longitude  DOUBLE PRECISION        -- WGS84
  geom            geometry(Point, 4326)        -- spatial index
  secret_hash     TEXT                         -- sha256 of provisioned secret
  cal_pm25_a, cal_pm25_b, cal_no2_a, cal_no2_b  DOUBLE PRECISION  -- calibration
  enrolled_at, last_seen  TIMESTAMPTZ

readings
  id              BIGSERIAL PRIMARY KEY
  sensor_id       TEXT REFERENCES sensors
  observed_at     TIMESTAMPTZ                  -- sensor clock
  pm25_raw, pm25, pm10_raw  DOUBLE PRECISION   -- raw and calibrated
  no2_raw, no2    DOUBLE PRECISION
  temperature_c, humidity_pct, pressure_hpa  DOUBLE PRECISION
  received_at     TIMESTAMPTZ                   -- backend clock

ward_polygons
  lganame, wardname  TEXT
  geom               geometry(MultiPolygon, 4326)
  PRIMARY KEY (lganame, wardname)
```

## What this backend does NOT do (yet)

- No MQTT ingest path. HTTP only. MQTT broker would be a Mosquitto sidecar; the firmware code in `Trellis/firmware/` includes the MQTT publisher that this backend would consume.
- No reading-rate-limit per sensor. Add Redis or a Postgres trigger.
- No retention policy. Readings accumulate forever. Add a cron-job that deletes readings older than N days.
- No timezone handling per ward. Sensor clocks are in UTC; that's fine for analysis but means the dashboard would need a tz-conversion layer for human-friendly "this morning" queries.
- No authentication for query endpoints. A real deployment should put the `/sensors`, `/readings`, `/wards/.../current` endpoints behind an auth middleware.

## Why this exists

Without a sensor backend, every channel (DHIS2, surge UI, school PWA, SMS dispatcher) needs its own data layer. The backend gives the platform one ingest point, one calibration rule, one ward-attribution rule, and one forecast endpoint. When a sensor wakes up, posts a reading, and goes back to sleep, that single value is now visible to every channel through the same API.
