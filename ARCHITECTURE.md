# Trellis architecture

This document is for engineers who want to understand how the Trellis components fit together. For a higher-level summary, see `README.md`. For the project's intended scope, see `trellis.md` (when authored) or `trellis_outline_proposal.md`.

## High-level data flow

```
   open EO data sources                ground sensors (25 nodes)
   ┌─────────────────────┐             ┌────────────────────────┐
   │ Sentinel-5P NO2     │             │ ESP32 + PMS5003 +      │
   │ CHIRPS rainfall     │             │ SGP41 + BME280         │
   │ NASA POWER temp     │             │ HMAC-signed POST       │
   │ GRID3 boundaries    │             └───────────┬────────────┘
   │ GGFR flares         │                         │
   │ GRID3 facilities    │                         ▼
   │ WorldPop population │             ┌────────────────────────┐
   │ Sentinel-2 NDVI     │             │ Sensor backend         │
   └──────────┬──────────┘             │ (FastAPI + Postgres +  │
              │                        │  PostGIS)              │
              ▼                        └───────────┬────────────┘
   ┌─────────────────────┐                         │
   │ Predictor table     │◀────────────────────────┘
   │ (ward × month, 36   │   ward attribution + readings
   │  cols, multi-year)  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ XGBoost forecast    │
   │ model               │
   └──────────┬──────────┘
              │
              ▼
       forecast_may_2026.json
              │
   ┌──────────┴──────────┬──────────────┬──────────────┬──────────────┐
   ▼                     ▼              ▼              ▼              ▼
DHIS2          School PWA          SMS         Surge UI         MCP server
dashboard      (PWA, offline)      dispatcher  (PHC supervisor) (LLM tools)
```

## Component-by-component

### `data/`

Open-data acquisition pipelines. Each subdirectory has a `build_*.py` script that pulls from a public source, clips to the pilot bbox, aggregates to ward-monthly, and writes a CSV. Per-source data cards (`*_DATA_CARD.md`) document provenance, license, schema, caveats.

### `model/`

XGBoost regressors for NO₂, rainfall, and temperature at month T+1 conditional on lagged climate features and per-ward static features. Walk-forward CV across 24 months. Trained models stored as `.joblib` artefacts. Skill report at `model/day1_skill_report.md`.

Re-train: `python3 train_model.py` (requires the multi-year predictor table at `data/predictors/trellis_ward_month_predictors_multiyear.csv`).

### `mvp/`

Single-page integrated dashboard with all four decision channels in tabs. Reads static JSON. Used during sprint-day demos. Replaced by the production-grade per-channel apps in `dhis2/`, `pwa-school/`, `surge/`, `sms/`.

### `dhis2/`

Two parts:

- `dhis2/index.html` — production-grade DHIS2-styled dashboard (full multi-view + filters + charts). Reads static JSON.
- `dhis2/local/` — self-host stack: docker-compose for DHIS2 + Postgres, build_orgunits to populate Nigeria's hierarchy, push_to_dhis2 to send forecasts as `dataValueSets`, and a DHIS2-aware variant of the dashboard that auto-detects DHIS2 vs static JSON.

### `pwa-school/`

Mobile-first Progressive Web App. Service worker (`sw.js`) caches assets and forecast for offline use. Manifest (`manifest.json`) supports "Add to home screen" install on phones. Single-page app with traffic-light alert + action checklist + 5-day outlook.

### `sms/`

FastAPI service that takes the forecast and dispatches SMS to enrolled caregivers when ward tier changes. SQLite for state. Pluggable provider with mock / Africa's Talking / Twilio adapters. Two languages (English + Nigerian Pidgin).

### `surge/`

Single-page web app for PHC supervisors. Ranked ward list by exposed-child-units priority. Per-ward detail with supervisor notes (localStorage). Weekly roster CSV export. Print-optimised morning brief view.

### `backend/`

The integration point. FastAPI + Postgres + PostGIS. Ingests sensor readings via HMAC-signed POST. Spatial-attributes them to wards. Applies per-sensor calibration. Exposes query endpoints. Proxies the forecast.

### `firmware/`

ESP32 sketch for the 25-node DePIN sensors. Forks AirGradient. Reads PM₂.₅, PM₁₀, NO₂, T, H, P every 60 s. Buffers and HMAC-posts every 5 min.

### `mcp/`

Model Context Protocol server. Exposes the platform as five LLM-callable tools (`trellis_forecast`, `trellis_ward_profile`, `trellis_alert_list`, `trellis_priority_score`, `trellis_send_advisory`). Connects to the backend; falls back to static JSON.

### `outreach/`

LoI templates (no specific recipients identified — see `outreach/loi_README.md`).

### `eoi_drafts/` and `trellis_md_drafts/`

Drafts of EOI sections and trellis.md sections respectively. The full trellis.md document does not yet exist; `trellis_outline_proposal.md` proposes its structure.

## Data flow patterns

### One-shot acquisition

```bash
cd data/no2 && python3 build_no2_baseline.py       # repeat for each layer
cd ../predictors && python3 build_predictors.py     # join into one table
cd ../../model && python3 train_model.py            # train and save
python3 forecast_may2026.py                          # produce next-month forecast
```

### Live-data flow with backend

```
sensor → backend.ingest → Postgres → backend.query
                                     │
                                     └→ forecast proxy → all four channels
```

### Forecast refresh cycle

```
new EO data lands → re-run build_predictors.py → re-train OR predict-only
    → write new forecast_may_2026.json → channels auto-detect on next page open
```

For DHIS2 + SMS dispatcher, an additional step: `python3 push_to_dhis2.py` to update DHIS2 dataValueSets, then `curl -X POST http://localhost:8000/dispatch` to fire any caregiver SMS for tier-changed wards.

## Authentication

| Surface | Auth |
|---|---|
| Backend ingest | Per-sensor HMAC-SHA256 |
| Backend query | None (assumes deployment behind reverse proxy with auth) |
| DHIS2 push | Basic auth to DHIS2 Web API |
| SMS dispatcher | None (assumes deployment behind firewall) |
| MCP server | Stdio-only; auth is handled by the MCP client |
| Frontend dashboards | None (read-only views) |

For production, the backend and SMS dispatcher should be behind an OAuth proxy; the dashboards should be behind authenticated reverse proxies (e.g. Caddy with OAuth, or DHIS2's own SSO when embedded as a custom app).

## Database choices

- **Postgres + PostGIS** for the sensor backend. PostGIS gives free spatial queries (`ST_Contains` for ward attribution).
- **SQLite** for the SMS dispatcher's enrollment + audit log. Single-file, no DB server needed for development.

## Deployment

For development, every component runs in Docker on `localhost`. For production, the recommended pattern is:

- All services behind a reverse proxy (Caddy, nginx, Traefik) on a single VPS to start
- Postgres backups via pg_dump nightly
- Forecast pipeline runs as a scheduled job (cron, systemd timer, GitHub Actions, or AWS EventBridge)
- Frontend dashboards served as static files
- MCP server on the same host as the backend for low-latency tool calls

A Kubernetes pattern works the same way at scale; the backend and SMS dispatcher are stateless behind the database and the SMS provider.

## Open architectural questions

- The forecast pipeline currently re-trains on every refresh. For production, separate the training run (weekly) from the prediction run (daily / on-trigger).
- The MCP server reads static JSON as fallback; in production it should always go through the backend so the latest forecast is canonical.
- The school PWA's notification path is missing; in production it would need a push-notification server or DHIS2-mediated push.
- DHIS2 integration is one-way (Trellis → DHIS2). For a true two-way integration the backend should subscribe to DHIS2 webhooks for facility metadata changes.
