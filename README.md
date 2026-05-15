# Trellis

**A structure that protects children while letting them grow.**

Open-source, child-centric platform for modelling the linkages between industrial pollution, environmental damage, and the health of populations exposed to them. Fuses satellite Earth Observation, ground-based DePIN sensors, and routine health-system data to issue **4-week-ahead, ward-resolution forecasts** of childhood malaria, asthma, acute respiratory infection, pneumonia, and pollution exposure — and renders the same forecast through four parallel decision channels: a DHIS2 dashboard for ministries of health, a mobile-first PWA for schools, SMS alerts to caregivers, and surge-planning outputs for primary care.

Pilot domain: five Delta State LGAs (Warri South, Warri South-West, Burutu, Bomadi, Patani) covering 51 wards, ~700,000 residents, ~109,000 children under 5.

## Status

Pre-EOI. Submission target: UNICEF Venture Fund 2026 Climate Ventures programme. No partnership commitments, no incorporation status claims — see `PARTNERSHIP_AUDIT.md` for an honest accounting of what's confirmed (essentially nothing) versus what's been built (essentially everything else).

## Repository layout

```
Trellis/
├── README.md                        ← this file
├── LICENSE                          ← MIT for software
├── LICENSE-DATA                     ← CC-BY 4.0 for data and docs
├── LICENSE-DHIS2                    ← GPL-3.0 for DHIS2 connectors
├── LICENSE-HARDWARE                 ← TAPR Open Hardware License for firmware
├── CONTRIBUTING.md
├── ARCHITECTURE.md
├── PARTNERSHIP_AUDIT.md             ← honest accounting of unconfirmed claims
├── day{1..5}_wrap.md                ← per-day sprint reports
│
├── data/                            ← open-data acquisition pipelines
│   ├── trellis_delta_wards.gpkg     ← 268 ward polygons (GRID3 v2.0)
│   ├── no2/                         ← Sentinel-5P NO₂ 91 monthly composites
│   ├── rainfall/                    ← CHIRPS 136 monthly composites
│   ├── temperature/                 ← NASA POWER daily/monthly
│   ├── flares/                      ← World Bank GGFR per-flare-site
│   ├── health/                      ← GRID3 health facilities + LGA boundaries
│   ├── population/                  ← WorldPop 1km
│   ├── ndvi/                        ← Sentinel-2 NDVI (partial; Sentinel-1 RVI documented)
│   ├── predictors/                  ← joint multi-year ward × month table (6,936 rows × 36 cols)
│   └── siting/                      ← composite priority score, weighting comparison, locked allocation
│
├── model/                           ← XGBoost forecast model
│   ├── train_model.py
│   ├── feature_table_multiyear.csv
│   ├── model_no2_umol_m2.joblib
│   ├── model_rainfall_mm.joblib
│   ├── model_t2m_mean.joblib
│   ├── forecast_may_2026_v2.csv
│   └── day1_skill_report.md         ← +48% NO₂ skill / +54% rainfall / +60% temp vs persistence
│
├── mvp/                             ← integrated dashboard for sprint-day demos
│   ├── index.html
│   ├── forecast_may_2026.json
│   └── (geojson + json data files)
│
├── dhis2/                           ← production DHIS2 dashboard
│   ├── index.html
│   ├── SETUP_LOCAL_DHIS2.md
│   └── local/                       ← self-host stack: docker-compose + push_to_dhis2 + dashboard
│
├── pwa-school/                      ← installable, offline-capable school advisory PWA
│   ├── index.html
│   ├── manifest.json
│   └── sw.js
│
├── sms/                             ← caregiver SMS dispatcher service (FastAPI)
│   ├── app.py
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── surge/                           ← primary-care supervisor surge planning UI
│   └── index.html
│
├── backend/                         ← sensor ingest backend (FastAPI + Postgres + PostGIS)
│   ├── app.py
│   ├── simulate_sensor.py
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── firmware/                        ← ESP32 sensor firmware (AirGradient-derived, HMAC-signed)
│   ├── platformio.ini
│   └── src/main.cpp
│
├── mcp/                             ← Trellis MCP server
│   ├── server.py
│   └── claude_desktop_config_snippet.json
│
├── outreach/                        ← LoI templates (no specific recipients identified)
│
├── eoi_drafts/                      ← UNICEF EOI section drafts
├── trellis_md_drafts/               ← per-section trellis.md drafts
└── trellis_outline_proposal.md      ← proposed 16-section trellis.md TOC
```

## What's implemented end-to-end

```
                ┌────────────────────────────────────────┐
                │   Open-data acquisition (data/)        │
                │   Sentinel-5P, CHIRPS, NASA POWER,     │
                │   GRID3, GGFR, WorldPop                │
                └─────────────────┬──────────────────────┘
                                  │
                                  ▼
                ┌────────────────────────────────────────┐
                │   Predictor table (6,936 rows × 36)    │
                │   Ward × month, multi-year             │
                └─────────────────┬──────────────────────┘
                                  │
                                  ▼
                ┌────────────────────────────────────────┐
                │   XGBoost forecast model               │
                │   +48% NO₂ skill vs persistence        │
                └─────────────────┬──────────────────────┘
                                  │
       ┌──────────────┬───────────┼──────────────┬──────────────────────┐
       ▼              ▼           ▼              ▼                       ▼
┌──────────┐ ┌──────────────┐ ┌────────┐ ┌────────────┐ ┌─────────────────┐
│  DHIS2   │ │ School PWA   │ │  SMS   │ │ Surge UI   │ │  Sensor backend │
│ dashboard│ │ (offline)    │ │ disp.  │ │ (PHC)      │ │  (FastAPI+Pg)   │
└──────────┘ └──────────────┘ └────────┘ └────────────┘ └────────┬────────┘
                                                                  │
                                                                  ▼
                                                         ┌─────────────────┐
                                                         │  ESP32 sensors  │
                                                         │  HMAC-signed    │
                                                         └─────────────────┘
```

All seven boxes have working code. The MCP server (`mcp/`) sits on top of the backend and exposes the whole platform as five LLM-callable tools.

## Quickstart — running the platform locally

```bash
# 1. Sensor backend + Postgres (for ingest, ward attribution, forecast proxy)
cd backend
docker compose up -d
sleep 15
curl -X POST http://localhost:8001/admin/load-wards
python3 simulate_sensor.py    # enrolls a synthetic sensor at Ekurede + sends 5 readings

# 2. SMS dispatcher (mock provider by default)
cd ../sms
cp ../mvp/forecast_may_2026.json forecast.json
docker compose up -d
curl -X POST http://localhost:8000/dispatch

# 3. DHIS2 self-host (optional — for ministry-style integration)
cd ../dhis2/local
docker compose up -d
sleep 60
python3 push_to_dhis2.py --setup
python3 push_to_dhis2.py

# 4. Open the dashboards
open dhis2/index.html         # ministry analyst view
open surge/index.html         # PHC supervisor view
cd pwa-school && python3 -m http.server 8081 &
open http://localhost:8081    # school administrator view, offline-capable

# 5. MCP server (optional — for AI-agent integration)
cd ../mcp
pip install -r requirements.txt
# Add claude_desktop_config_snippet.json to your Claude Desktop config
```

## Forecast model

| Target | Model RMSE | Persistence RMSE | Skill vs persistence | Climatology RMSE | Skill vs climatology |
|---|---|---|---|---|---|
| NO₂ (μmol/m²) | 4.57 | 8.81 | **+48.1%** | 6.36 | **+28.1%** |
| Rainfall (mm/month) | 69.3 | 151.6 | **+54.3%** | 112.3 | **+38.3%** |
| Temperature (°C) | 0.35 | 0.87 | **+60.0%** | 0.70 | **+50.0%** |

XGBoost ensemble, walk-forward time-series CV across 24 months, trained on 91 months of Sentinel-5P NO₂ + 136 months of CHIRPS rainfall + 76 months of NASA POWER temperature, plus per-ward static features (population, U5 children, health facilities, gas-flare exposure, NDVI).

Top features for NO₂ forecast: month_cos (0.63), ndvi_annual (0.12), month_sin (0.12), t2m_mean_lag3 (0.03), fac_phc (0.02). Seasonal cycle dominates; vegetation regime and PHC density are second-order modifiers.

## Sensor allocation

25 nodes across 51 wards, allocated 10 PHC + 10 school + 5 community. Allocation is driven by a transparent composite ward score (35% child population, 25% NO₂, 25% coverage gap, 15% flares). Verified robust under three alternative weightings — 14 of 25 placements unchanged in the stable core. The three pilot wards with zero health facilities (Akpakpa, Akugbene 2, Patani 2) all receive a community node; the equity guard is structural, not negotiated.

See `data/siting/sensor_allocation_proposal.md` for the full proposal and `data/siting/sensor_allocation.csv` for the locked node-by-node table.

## Three novelty levers

1. **Sub-district resolution via satellite + DePIN fusion** — ward (admin-3) forecasts, validated by ground sensors that fill the 12 wards where Sentinel-5P has no pixel coverage.
2. **Cross-domain Niger-Delta-specific EO stack** — NO₂ × rainfall × temperature × flare × NDVI × population × facilities, in one ward × month matrix, all open data.
3. **Open MCP server architecture** — Trellis exposes itself as a uniform agent-callable interface (`mcp/server.py`), so an LLM-powered assistant can answer any question the dashboard could without custom integration.

## Licensing

| Component | License | Why |
|---|---|---|
| Software (`mvp/`, `dhis2/`, `pwa-school/`, `surge/`, `sms/`, `backend/`, `mcp/`, `model/`) | MIT | Maximum reuse |
| DHIS2 connectors (`dhis2/local/push_to_dhis2.py`, `dhis2/SETUP_LOCAL_DHIS2.md`) | GPL-3.0 | Compatible with DHIS2 core |
| Data and documentation (`data/`, `*_DATA_CARD.md`) | CC-BY 4.0 | Open-data norm |
| Sensor firmware (`firmware/`) | TAPR Open Hardware License | Inherited from AirGradient base |

## Acknowledgements

Built on:
- AirGradient open-hardware reference design
- DHIS2 platform (HISP)
- Sentinel-5P / Sentinel-2 / Sentinel-1 (Copernicus / ESA)
- CHIRPS (UCSB Climate Hazards Center)
- NASA POWER project / MERRA-2 reanalysis
- World Bank Global Gas Flaring Reduction Partnership
- WorldPop (University of Southampton)
- GRID3 Nigeria

Influenced by:
- Snow (1854) — place-based determinants
- Belsky et al. (2019, *Nature Human Behaviour*) — geography of health
- Wimberly EPIDEMIA (Ethiopia malaria forecasting)
- Allegheny County Pediatric Asthma Study (UPMC)
- WHO EWARS

## Contributing

See `CONTRIBUTING.md`. Open-source contributions are welcome especially for:

- DHIS2 metadata pack improvements
- Africa-specific localisations of the school advisory PWA and SMS templates
- Additional EO predictor pulls (the platform's pipeline is extensible — see `data/build_*.py`)
- Hardware add-ons for the firmware (CO₂, PM₁, additional NO₂ cells)
- Forecast model improvements (we expect strong gains from multi-year cross-validation refinements)
