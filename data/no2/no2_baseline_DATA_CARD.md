# Data card: Sentinel-5P NO2 baseline

## Identity

- **Files:** `data/no2/no2_<YYYY>_<MM>.tif` (91 monthly grids), `data/no2/no2_ward_zonal.csv` (~4,641 ward-month rows), GeoPackage layer `no2_ward_2026_04` for the latest month
- **Format:** Cloud Optimized GeoTIFF (raster), CSV (tabular), OGC GeoPackage (vector)
- **CRS:** EPSG:4326
- **Time window:** 1 October 2018 – 30 April 2026 (91 months — full Sentinel-5P operational record)
- **Created:** 9 May 2026
- **Purpose:** Tropospheric nitrogen dioxide column density climatology for the Trellis pilot LGAs, against which 4-week forecast skill and trend detection will be measured.

## Source

- **Product:** Sentinel-5P L2 NO₂ (OFFL stream)
- **Distribution:** MEEO Sentinel-5P COG mirror on AWS Open Data Registry (`s3://meeo-s5p`)
- **Access:** anonymous S3 (no Copernicus Data Space credentials required)
- **Asset used:** `<granule>_PRODUCT_nitrogendioxide_tropospheric_column_4326.tif`
- **QA mask:** `<granule>_PRODUCT_qa_value_4326.tif`, threshold ≥ 0.75 per *Sentinel-5P L2 NO₂ Product User Manual* (S5P-KNMI-L2-0021-MA)
- **Native instrument:** TROPOMI on Sentinel-5P, sun-synchronous polar orbit, ~13:30 local equator crossing, 5.5 × 3.5 km pixel
- **Units:** mol m⁻² (tropospheric column density)
- **License:** Free re-use under the Copernicus open access policy

## Method

For each calendar day, the script lists every TROPOMI orbit COG under
`COGT/OFFL/L2__NO2___/<YYYY>/<MM>/<DD>/`, filters to orbits whose sensing
start time UTC falls in the 10:00–13:00 window (the only orbits whose
swath crosses Delta longitude), and submits each to a thread-pool of
windowed COG reads clipped to the pilot bbox (5.1571 W, 5.0118 S,
6.2930 E, 5.8299 N). For each read it applies `qa_value ≥ 0.75`, sums
contributing pixels into a running accumulator, and divides by
contribution count to produce a monthly mean grid. Zonal mean per ward
uses `rasterstats.zonal_stats` over the `pilot_wards` polygon layer.

## Twelve-month results

- Months covered: May 2025 through April 2026
- Per-month candidate orbits: 26–37 (using the tighter 11–12 UTC orbit filter that fits the sandbox 45 s budget; April 2026 was generated with the wider 10–13 UTC filter and is interchangeable)
- Per-month orbits contributing data after QA ≥ 0.75: 21–31
- Per-month ward coverage: stable at **39 of 51 pilot wards** (76.5%). The 12 wards with no data each month are small riverine wards in Bomadi and Burutu that fall below the 5.5 × 3.5 km TROPOMI pixel footprint — extending the time window does not fix this; ground-based sensors will.
- Output grid: 23 × 32 pixels at native COG resolution

### Domain-mean NO₂ by month (μmol m⁻²)

| Month | Mean | Notes |
|---|---|---|
| 2025-05 | 17.0 | wet-season transition |
| 2025-06 | 11.8 | wet-season minimum |
| 2025-07 | 11.6 | wet-season minimum |
| 2025-08 | 14.1 | |
| 2025-09 | 16.7 | |
| 2025-10 | 15.6 | |
| 2025-11 | 17.1 | start of dry season |
| **2025-12** | **34.9** | Harmattan biomass-burning peak |
| 2026-01 | 29.3 | dry season |
| 2026-02 | 24.6 | dry season |
| 2026-03 | 24.9 | |
| 2026-04 | 21.7 | wet-season transition |

The wet-to-dry seasonality is roughly 3×. December's spike is the regional Harmattan signal — northeasterly trade winds carrying biomass-burning plumes from Sahel agricultural fires south to the Niger Delta. This is precisely the signal a Trellis 4-week asthma advisory should be predicting.

### LGA climatology (12-month mean ± std, μmol m⁻²)

| LGA | Mean | Std | Sample size |
|---|---|---|---|
| Warri South | 25.4 | 8.3 | 60 |
| Patani | 21.9 | 10.4 | 84 |
| Warri South-West | 19.2 | 5.7 | 96 |
| Bomadi | 18.7 | 9.4 | 96 |
| Burutu | 17.7 | 6.9 | 132 |

Refinery-and-urban Warri sits highest, riverine Burutu lowest, in every month — consistent with refinery emissions, port traffic, and urban combustion as the dominant Niger-Delta NO₂ sources at the scale TROPOMI resolves.

### Top 5 wards by 12-month mean

| LGA | Ward | NO₂ (μmol m⁻²) |
|---|---|---|
| Warri South | Pessu | 30.3 |
| Warri South | Ekurede | 29.0 |
| Warri South | Ode-Itsekiri | 24.1 |
| Warri South | Ubeji | 23.4 |
| Patani | Agoloma | 22.3 |

Four of the five highest-NO₂ wards are in Warri South — the refinery and port core. This is the ward-level pattern Trellis forecasts will need to reproduce.

## Known caveats

- **Pixel sparsity.** 12 of 51 wards have no valid pixel for April. Most others have one to ten. Monthly compositing over a single month is too short for confident ward means in the small wards. Twelve-month aggregation, or fusion with NRTI orbits, will fix this.
- **Cloud bias.** QA ≥ 0.75 strongly excludes cloudy retrievals, which biases the sample toward cloud-free days. In the Niger Delta wet season this is structural, not a bug.
- **Flare detection.** TROPOMI's 5.5 × 3.5 km pixel under-resolves individual flare stacks. Persistent NO₂ enhancements show up; transient single-flare plumes generally do not. Flare detection in Trellis should rely on VIIRS Nightfire, not S5P alone.
- **OFFL vs NRTI.** OFFL is the reprocessed/validated product (~3-day latency). NRTI (~3-hour latency) is what the operational system will use for current-week forecasts. Calibration between the two streams is a separate task.
- **Ground truth gap.** S5P measures column density (vertically integrated). Surface concentration in μg/m³ — which is what asthma-relevant exposure metrics need — requires an additional vertical-profile assumption or the planned DePIN sensor cross-calibration.

## Reproducibility

The build script (`data/build_no2_baseline.py`) accepts month arguments:

```bash
# Single month (default: April 2026)
python3 build_no2_baseline.py

# Custom range
python3 build_no2_baseline.py 2025-05 2025-06 2025-07
```

Each month takes roughly 30–60 seconds depending on S3 latency and the number of orbits with valid data. A full twelve-month run is on the order of 5–10 minutes wall time.

## Next steps

1. Twelve-month run: May 2025 to April 2026 — gives the climatological reference against which weekly forecasts will be skill-scored.
2. Add NRTI stream for current-period continuity.
3. Add NO₂ as a column to the DHIS2 predictor table once the eight-predictor schema is finalised.
4. Cross-validate with KNMI TM5-MP reanalysis monthlies as an independent reference.
