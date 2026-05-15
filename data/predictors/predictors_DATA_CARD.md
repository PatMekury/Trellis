# Data card: joint ward-month predictor table

## Identity

- **File:** `data/predictors/trellis_ward_month_predictors.csv` (612 rows × 40 columns)
- **GeoPackage layer:** `predictors_ward_month_2026_04` (latest-month polygon view)
- **Build script:** `data/predictors/build_predictors.py`
- **Format:** CSV (tabular), OGC GeoPackage (vector)
- **CRS:** EPSG:4326
- **Time window:** 1 January 2015 – 30 April 2026 (multi-year, with NO₂ from October 2018 onwards and temperature from January 2020 onwards)
- **Created:** 9 May 2026
- **Purpose:** Single tidy ward × month matrix consolidating four predictors acquired in this session. The starting point for the 8-predictor schema described in the trellis.md methodology.

## Schema

51 pilot wards × 136 months = 6,936 rows. One row per ward per month. NO₂ is non-null for the 91 months Sentinel-5P has been operating; temperature is non-null for the 76 months NASA POWER provides; rainfall is non-null for all 136 months.

### Keys

| Column | Type | Description |
|---|---|---|
| `lganame` | str | LGA name (one of: Warri South, Warri South-West, Burutu, Bomadi, Patani) |
| `wardname` | str | Ward name within LGA |
| `ym` | str | "YYYY-MM" formatted year-month |
| `year`, `month` | int | Calendar year and 1–12 month |

### Time-varying predictors (vary across the 12 months)

| Column | Source | Units | Description |
|---|---|---|---|
| `no2_mol_m2` | Sentinel-5P L2 NO₂ via MEEO COG | mol m⁻² | Tropospheric column density, monthly mean (QA ≥ 0.75) |
| `no2_umol_m2` | derived | μmol m⁻² | Convenience: same value × 10⁶ |
| `no2_valid_pixels` | derived | count | TROPOMI pixels passing QA in the ward × month |
| `rainfall_mm` | CHIRPS v2.0 Africa monthly | mm/month | Total rainfall for the month |
| `rainfall_valid_pixels` | derived | count | CHIRPS pixels intersecting the ward |
| `t2m_mean` | NASA POWER (MERRA-2) | °C | Monthly mean of daily 2-m air temperature |
| `t2m_max` | NASA POWER | °C | Highest daily max in the month |
| `t2m_min` | NASA POWER | °C | Lowest daily min in the month |
| `ts_mean` | NASA POWER | °C | Monthly mean of daily skin temperature |
| `temp_n_days` | derived | count | Days contributing to the monthly aggregates |
| `rainfall_mm_lag1m` | derived | mm/month | Rainfall in the prior month (~4 weeks lag) |
| `rainfall_mm_lag2m` | derived | mm/month | Rainfall 2 months prior (~8 weeks lag) |
| `rainfall_mm_lag3m` | derived | mm/month | Rainfall 3 months prior (~12 weeks lag) |
| `t2m_mean_lag1m` | derived | °C | T2M in the prior month |
| `t2m_mean_lag2m` | derived | °C | T2M 2 months prior |
| `t2m_mean_lag3m` | derived | °C | T2M 3 months prior |

The lagged columns are NaN for the leading edge of the time window (May 2025 has no 1-month lag, June 2025 no 2-month lag, etc.). Coverage is 91.7% / 83.3% / 75.0% for 1m / 2m / 3m lags respectively. To eliminate these gaps for a production model, extend the underlying CHIRPS and POWER pulls back by three additional months.

### Static predictors (broadcast across all 12 months for a given ward)

| Column | Source | Units | Description |
|---|---|---|---|
| `flare_n_sites` | World Bank GGFR | count | Number of distinct GGFR flare sites within the ward (2012–2024 catalog) |
| `flare_total_bcm_13yr` | GGFR | BCM | Sum of cumulative flaring volume across all sites in the ward |
| `flare_max_site_bcm` | GGFR | BCM | Largest single flare site in the ward |
| `flare_last_year_bcm` | GGFR | BCM | Sum of last-active-year volume across the ward's sites |
| `flare_operators` | GGFR | str | Comma-separated operators present |
| `fac_total` | GRID3 NHFR | count | Total health facilities |
| `fac_phc` | GRID3 NHFR | count | Primary (PHC) facilities |
| `fac_secondary` | GRID3 NHFR | count | Secondary facilities |
| `fac_tertiary` | GRID3 NHFR | count | Tertiary facilities |
| `fac_public` | GRID3 NHFR | count | Publicly owned facilities |
| `fac_private` | GRID3 NHFR | count | Privately owned facilities |
| `pop_total` | WorldPop 1km 2024 | count | Total ward population |
| `pop_under5` | derived | count | `pop_total × 0.156` (Nigeria national U5 fraction, UN WPP 2024) |
| `fac_per_1k_pop` | derived | rate | Facilities per 1,000 residents |
| `phc_per_1k_u5` | derived | rate | PHCs per 1,000 children under 5 |
| `ndvi_annual` | Sentinel-2 L2A | unitless | Annual median NDVI per ward (static) |
| `ndvi_monthly` | Sentinel-2 L2A | unitless | Monthly NDVI for the ward × month, where a composite exists |
| `ndvi` | derived | unitless | `ndvi_monthly` if present, else `ndvi_annual` |
| `ndvi_source` | derived | str | "monthly" or "annual" — which value `ndvi` came from |

## Coverage at a glance

| Predictor | Ward-months with data | % of 612 |
|---|---|---|
| Rainfall | 612 | 100.0% |
| Temperature | 612 | 100.0% |
| Population (≥ 1 person) | 588 | 96.1% |
| Health facility (≥ 1) | 576 | 94.1% |
| NO₂ | 468 | 76.5% |
| Flares (≥ 1) | 96 | 15.7% |

NO₂ has 24 ward-months × 12 wards = ~144 missing cells in 12 wards that fall below TROPOMI's pixel footprint (small riverine wards in Bomadi, Burutu). Flares are 8 wards × 12 months = 96 — the rest legitimately have no GGFR-recorded persistent flare. The flare and NO₂ gaps are *inverse-correlated* exactly where Trellis needs them to be: many flare-bearing Burutu wards lack S5P pixels, but have flare records, so the joint signal still covers them.

## LGA snapshot

| LGA | Wards | NO₂ mean (μmol/m²) | Rainfall mean (mm/month) | Flare BCM 2012–2024 | Total facilities |
|---|---|---|---|---|---|
| Warri South | 10 | 25.4 | 213 | 0.00 | 77 |
| Patani | 10 | 21.9 | 215 | 0.00 | 18 |
| Warri South-West | 10 | 19.2 | 112* | 3.81 | 23 |
| Bomadi | 10 | 18.7 | 226 | 0.00 | 21 |
| Burutu | 11 | 17.7 | 231 | 0.24 | 37 |

(* The Warri South-West rainfall mean is depressed by coastal pixels; see the rainfall data card for the methodological caveat.)

This single table tells the headline story of the pilot domain. **Warri South** is the urban-and-refinery LGA: highest NO₂, highest facility density, no GGFR-classified flares but the most exposed urban combustion. **Warri South-West** is the offshore-feed terminal LGA: most flaring by a wide margin, low rainfall (coastal artefact), moderate NO₂. **Burutu** is the riverine-and-flaring LGA: most rainfall, most TROPOMI gaps, the second-most flares, second-most facilities. **Bomadi** and **Patani** are the rural baseline LGAs: lowest NO₂, no flares, moderate facility density.

## Path to the eight-predictor schema

The trellis.md methodology section commits to eight DHIS2 predictors at deployment. Status of each as of this session:

| # | Predictor | Status |
|---|---|---|
| 1 | Sentinel-5P NO₂ | **Done** — 91 months (Oct 2018 – Apr 2026), ward-monthly |
| 2 | CHIRPS rainfall | **Done** — 136 months (Jan 2015 – Apr 2026), ward-monthly |
| 3 | GGFR / VIIRS flare exposure | **Done** — 13-year cumulative + per-ward |
| 4 | Health-facility geography | **Done** — count + ownership + level by ward |
| 5 | Temperature (heat) | **Done** — NASA POWER 2-m air temperature, daily aggregated to monthly. MODIS LST is a future cross-check when Earthdata credentials are in place. |
| 6 | Sentinel-2 NDVI vegetation | **Partial** — annual + 3 monthly composites; combined ward-month coverage 43.8%. Anonymous Sentinel-2 windowed reads are bandwidth-bound in the sandbox; production path is GEE or Sentinel Hub Statistical API. |
| 7 | Population density | **Done** — WorldPop 1 km 2024 constrained UA, with derived under-5 estimate. |
| 8 | DHIS2 historical health outcomes | Not yet accessible. Requires a state-level data-sharing arrangement to be identified and negotiated. |

The first four are open-data; the next two are open-data and would slot in identically (one EO product → ward-monthly via the same windowed-COG-read pattern). Population is also open-data. Only #8 requires a partnership.

## Caveats on joining static and time-varying

The static predictors (flares, facilities) are broadcast across all 12 months, which means a model fit on this table will see no temporal variation in those columns and will treat them as fixed offsets. That is correct: GGFR is annual at finest, and facility counts change on year-scale, not month-scale. When the daily VNF stream and live NHFR updates are wired in, those columns become time-varying.

## Caveats on coverage gaps

NO₂ ward-mont