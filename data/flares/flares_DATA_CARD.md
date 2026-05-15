# Data card: GGFR gas flare layer

## Identity

- **Files:**
  - `data/flares/ggfr_flare_locations_2012_2024.xlsx` — source archive
  - `data/flares/delta_flare_sites.gpkg` — point layer of 442 Delta flare sites (single-layer GeoPackage)
  - `data/flares/delta_ward_flare_summary.csv` — per-ward summary table
  - `data/flares/preview/flares_pilot_overview.png` — two-panel map preview
  - `data/flares/build_ggfr_flares.py` — reproducible build script
  - GeoPackage layers in `trellis_delta_wards.gpkg`: `delta_flare_sites` (442 points) and `ward_flare_summary` (51 pilot wards with flare metrics)
- **Format:** XLSX (source), OGC GeoPackage (vector), CSV (tabular), PNG (preview)
- **CRS:** EPSG:4326
- **Time window:** 2012–2024 (annual)
- **Created:** 9 May 2026
- **Purpose:** Persistent gas flare site inventory and ward-level flaring intensity. Foundation for the asthma-exposure baseline and a candidate priority surface for sensor-siting in pilot LGAs.

## Source

- **Dataset:** *Global Gas Flaring Tracker — 2012–2024 Flare Volume Estimates by Individual Flare Location* (XLSX, ~14 MB, ~156k rows globally)
- **Publisher:** World Bank Global Gas Flaring Reduction Partnership (GGFR), produced in collaboration with NOAA Earth Observation Group / Colorado School of Mines
- **Release:** July 2025 (covers calendar years 2012 through 2024)
- **Method:** VIIRS Nightfire (multi-band thermal detection on Suomi-NPP and NOAA-20) with country-level calibration. Each row is one (lat, lon) flare site for one calendar year, with annual BCM volume.
- **URL used:** https://thedocs.worldbank.org/en/doc/bd2432bbb0e514986f382f61b14b2608-0400072025/related/2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx
- **Access:** open, anonymous HTTPS download, no registration
- **License:** open data, World Bank Open Data License (CC-BY 4.0)

## Why this layer instead of FIRMS / VNF daily

The canonical NOAA EOG VIIRS Nightfire (VNF) product gives daily detections with radiant heat (MW), temperature (K), and source persistence — better for current-period operational forecasting. As of January 2025, VNF requires a free NOAA EOG account; FIRMS API requires a free MAP_KEY. Both are user-credentialed and cannot be pulled in this session.

The GGFR dataset is the same VNF product, distilled by the EOG team to per-site annual volumes and published openly through the World Bank. For Trellis at the EOI stage, this is the right layer: it identifies *where* the persistent flares are, *how big* they are over a multi-year window, and *which ward* they fall in. Daily VNF and FIRMS plug in later for the current-week operational signal.

## Schema

**Site layer (`delta_flare_sites`)**

| Field | Description |
|---|---|
| `Latitude`, `Longitude` | Decimal degrees, EPSG:4326 |
| `total_bcm_2012_2024` | Cumulative flaring volume across all detected years, billion cubic metres |
| `mean_bcm_per_active_year` | Mean BCM per year *only over years the site was detected* |
| `n_years_active` | Number of distinct years with a detection (1–13) |
| `first_year`, `last_year` | First and last year of detection |
| `last_bcm` | Volume in the most recent active year |
| `field_name`, `operator`, `field_type`, `location_type` | GGFR-supplied operator metadata where available |
| `wardname`, `lganame` | Joined from `delta_wards` via spatial within |

**Ward summary layer (`ward_flare_summary`)** — one row per pilot ward

| Field | Description |
|---|---|
| `n_flare_sites` | Number of distinct flare sites within the ward polygon |
| `total_bcm_13yr` | Sum of cumulative flaring volume across all sites in the ward |
| `max_site_bcm` | Largest single site within the ward |
| `last_year_bcm` | Sum of last-year volume across the ward's sites |
| `operators` | Comma-separated list of distinct operators with sites in the ward |

## Coverage and signal

- **Nigeria total:** 1,734 unique flare sites, 2,264 site-year records 2012–2024.
- **Delta State:** 442 sites within the operational ward polygons.
  - 295 sites with cumulative BCM ≥ 0.01 (10 million m³) over 13 years — the "meaningful" flares.
  - 59 sites with cumulative BCM ≥ 0.1 (100 million m³) — the major persistent flares.
- **Pilot wards with any flare:** 8 of 51 — concentrated in Warri South-West (the Escravos coastal corridor) and Burutu (Ogulagha).

### Top pilot wards by 2012–2024 cumulative flaring (BCM)

| LGA | Ward | Sites | Total BCM | Largest single site (BCM) |
|---|---|---|---|---|
| Warri South-West | Ogbe-Ijoh | 26 | 1.140 | 0.164 |
| Warri South-West | Ugborodo | 20 | 1.054 | 0.191 |
| Warri South-West | Okerenkoko | 26 | 0.900 | 0.242 |
| Warri South-West | Ogidigben | 10 | 0.540 | 0.275 |
| Burutu | Ogulagha | 38 | 0.242 | 0.045 |
| Warri South-West | Oporozo | 9 | 0.163 | 0.101 |
| Warri South-West | Ajudaibo | 3 | 0.008 | 0.008 |
| Warri South | Obodo | 1 | 0.001 | 0.001 |

### Major operators in the pilot wards

Shell Petroleum Development Company, Chevron Nigeria Limited, NPDC (Nigerian Petroleum Development Company), SEPLAT Petroleum Development, Eni, Energia, Platform Petroleum.

## Cross-reference to the NO₂ layer

The flare layer complements the Sentinel-5P NO₂ baseline in two important ways. First, several pilot wards with no S5P pixel coverage (Bomadi and Burutu riverine wards smaller than the 5.5 × 3.5 km TROPOMI footprint) *do* have flares in the GGFR record — for example, Burutu's Ogulagha has 38 sites despite no NO₂ data. Second, the NO₂ ranking and the flare ranking diverge: NO₂ is highest in Warri South (urban/refinery NOₓ from combustion sources), while flaring is highest in Warri South-West (offshore-feeding terminal area at Escravos). Both are real Niger Delta exposure pathways and the platform should treat them as distinct predictors.

## Caveats

- **Annual resolution.** This dataset is one observation per site per year. It cannot drive a 4-week operational forecast on its own; it is the prior over which daily VNF / FIRMS detections will update.
- **Detection threshold.** GGFR / VNF only retains sites with a thermally-detectable flame. Cold vents, intermittent flares below threshold, and very-short-duration flares can be missed.
- **Site location uncertainty.** Reported coordinates are the centroid of detected pixels. For tightly-clustered flare stacks at one terminal, a single GGFR row may aggregate multiple physical stacks, or two physical stacks may be duplicated as separate rows in different years.
- **Operator attribution.** The `Field Operator` field is best-effort linkage by the EOG team; minor operators or wells changing hands across years can be miscredited.
- **Scope of "flaring."** The dataset is upstream-petroleum flaring. It excludes refinery flares, LNG terminal vents (mostly), and biomass burning — separate signals that NO₂ does pick up.

## Reproducibility

```bash
cd data/flares
curl -sL -o ggfr_flare_locations_2012_2024.xlsx \
  "https://thedocs.worldbank.org/en/doc/bd2432bbb0e514986f382f61b14b2608-0400072025/related/2012-2024-Flare-Volume-Estimates-by-individual-Flare-Location.xlsx"
python3 build_ggfr_flares.py
```

The build script depends on `pandas`, `openpyxl`, `geopandas`, `shapely`. Run from the `data/flares` directory; uses `/tmp/trellis_delta_wards.gpkg` as the boundary input (warmed up by any prior run of the wards build).

## Next steps

1. **Get NOAA EOG account** for daily VNF — gives current-week flare intensity (MW radiant heat) and per-stack persistence, the operational signal.
2. **Pair with Sentinel-3 SLSTR** Active Fire L2 (FRP_IN, FRP_NF) for an independent cross-check.
3. **Extend backwards** with the older OGRC flaring archive for longer-term trends.
4. **Cross-validate** ward-level total_bcm_13yr against NNPC and DPR (now NUPRC) reported flaring volumes for selected fields.
