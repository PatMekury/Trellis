# Data card: NASA POWER temperature baseline

## Identity

- **Files:**
  - `data/temperature/ward_temperature_daily.csv` — 18,615 rows of ward × day temperature values
  - `data/temperature/ward_temperature_monthly.csv` — 612 rows of ward × month aggregates
  - `data/temperature/build_temperature.py` — reproducible build script
- **Format:** CSV (tabular)
- **Time window:** 1 January 2020 – 30 April 2026 (76 months, daily resolution)
- **Created:** 9 May 2026
- **Purpose:** Air-temperature predictor for the Trellis pilot domain. Heat is a canonical malaria-vector covariate (Anopheles thermal envelope), an asthma-trigger covariate (heat-exacerbated airway reactivity), and a heat-stress covariate for child health more broadly.

## Source

- **Dataset:** NASA POWER (Prediction Of Worldwide Energy Resources), daily point timeseries
- **Underlying model:** MERRA-2 reanalysis (NASA GMAO), 0.5° × 0.625° global grid, downscaled and bias-adjusted by the POWER team
- **Endpoint:** `https://power.larc.nasa.gov/api/temporal/daily/point`
- **Parameters used:** `T2M` (2-metre air temperature, °C), `T2M_MAX`, `T2M_MIN`, `TS` (skin / land surface temperature, °C)
- **Community:** RE (Renewable Energy parameter set; same temperature variables as AG community)
- **Access:** open, anonymous REST API, no registration
- **License:** open data, NASA Open Data policy

## Why NASA POWER and not MODIS LST

The trellis.md predictor list calls for "MODIS LST". MODIS Land Surface Temperature (MOD11/MYD11 products) requires a NASA Earthdata Login and either bulk HDF download via LP DAAC or Google Earth Engine — both behind authentication walls that this acquisition session cannot pass anonymously. NASA POWER's MERRA-2-derived temperature is a defensible substitute for the climatology baseline:

- Same source family (NASA reanalysis)
- 2-m air temperature is arguably *more* relevant to childhood respiratory and vector exposure than skin LST, since human exposure is at body height
- POWER is calibrated against ground stations
- Provides daily resolution through ≤2 days of the present, which is what the operational forecast window needs

When Earthdata credentials are available, MODIS MOD11C3 monthly LST can be added as a complementary layer at 0.05° native resolution. The two are usually within 1 K of each other over flat coastal terrain (Liu et al., 2022, *Sci. Data*). They tend to diverge over dense canopy (LST reads warmer) and over urban areas (LST reads warmer due to surface heating).

## Schema

**Daily file (`ward_temperature_daily.csv`)**

| Column | Description |
|---|---|
| `lganame`, `wardname` | Ward identifier |
| `date` | YYYY-MM-DD |
| `t2m_c` | 2-m air temperature (°C, daily mean) |
| `t2m_max_c`, `t2m_min_c` | Daily max / min |
| `ts_c` | Skin temperature (°C, daily mean) |

**Monthly file (`ward_temperature_monthly.csv`)** — derived

| Column | Description |
|---|---|
| `lganame`, `wardname`, `year`, `month` | Keys |
| `t2m_mean` | Monthly mean of daily T2M (°C) |
| `t2m_max` | Highest daily max in the month |
| `t2m_min` | Lowest daily min in the month |
| `ts_mean` | Monthly mean of daily TS (°C) |
| `n_days` | Days contributing to the monthly mean |

## Twelve-month results

### Domain-mean T2M by month (°C)

| Month | T2M | Notes |
|---|---|---|
| 2025-05 | 27.0 | wet-season transition |
| 2025-06 | 26.3 | early wet season |
| 2025-07 | 25.2 | |
| 2025-08 | **24.9** | wet-season minimum (cloud cover, August Break) |
| 2025-09 | 25.3 | |
| 2025-10 | 25.8 | |
| 2025-11 | 26.9 | dry-down |
| 2025-12 | 26.8 | |
| 2026-01 | 27.1 | dry season |
| 2026-02 | 27.3 | |
| 2026-03 | **27.7** | dry-season maximum |
| 2026-04 | 27.6 | |

The 2.8 °C wet-to-dry seasonal cycle is small in absolute terms but matters for vector dynamics: *Anopheles* development and survival rates change non-linearly through the 24–28 °C range that this domain occupies year-round.

### LGA-mean T2M (12-month mean ± std, °C)

| LGA | Mean | Std |
|---|---|---|
| Warri South-West | 27.0 | 1.1 |
| Bomadi | 26.4 | 0.9 |
| Burutu | 26.4 | 0.9 |
| Patani | 26.4 | 0.9 |
| Warri South | 26.3 | 0.9 |

LGA-level differences are small (0.6 °C between extremes) because the underlying MERRA-2 grid is 0.5° (~50 km), coarser than the LGA polygons. Warri South-West appears warmer because more of its centroid mass is closer to the open ocean, where MERRA-2 grids slightly higher SSTs in this season.

## Cross-reference to NO₂ and rainfall

T2M is **inverse to rainfall** (cool wet season, warm dry season) and **co-varies with NO₂** (warm dry months are also high-NO₂ Harmattan months). Concretely:

| Month | T2M (°C) | Rainfall (mm) | NO₂ (μmol/m²) |
|---|---|---|---|
| Aug 2025 | 24.9 | 166 | 14.1 |
| Mar 2026 | 27.7 | 120 | 24.9 |

The cool-wet-low-NO₂ vs warm-dry-high-NO₂ correlation is exactly what a forecast model needs: temperature is a strong predictor of seasonal exposure regime, and the joint signal of T2M + rainfall + NO₂ should let the model classify the four-week-ahead state more reliably than any one alone.

## Caveats

- **Spatial resolution.** The native MERRA-2 grid is 0.5°, much coarser than the ward polygons. The POWER point endpoint interpolates bilinearly to the requested coordinate, so values differ smoothly across wards but the underlying signal is at LGA scale or coarser.
- **Reanalysis vs satellite.** This is reanalysis (model-blended) rather than direct observation. Spatial gradients are smoother than what direct sensor measurements would show, especially around urban heat islands and deforestation patches.
- **Time lag.** POWER daily updates with ~2-day latency. For real-time operational use this is fine; for "this morning" forecasts it is not.
- **Skin vs air.** `t2m` (air) and `ts` (skin) are different signals. Skin temperature peaks higher mid-day and drops lower at night than 2-m air. For exposure modelling, t2m is the right choice; ts is included for cross-validation against MODIS LST when Earthdata access is in place.
- **Future replacement.** When MODIS LST monthly comes online, prefer MOD11C3 for the static climatology and POWER T2M for the operational sliding window — they answer different questions.

## Reproducibility

```bash
cd data/temperature
python3 build_temperature.py
```

Pulls 51 ward centroids in parallel (12 threads), aggregates daily to monthly. Total wall time ~6 seconds.

## Next steps

1. **MODIS MOD11C3 LST** when Earthdata credentials are in place. Cross-check at LGA level against POWER T2M.
2. **Lagged temperature columns** for malaria modelling. The literature consistently uses 4–8 week lagged temperature alongside lagged rainfall.
3. **Heat-index derivation.** With T2M and humidity (POWER also provides RH2M), derive an apparent-temperature / heat-index column for direct heat-stress exposure framing.
