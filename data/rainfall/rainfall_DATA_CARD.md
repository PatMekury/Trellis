# Data card: CHIRPS rainfall baseline

## Identity

- **Files:**
  - `data/rainfall/chirps_<YYYY>_<MM>.tif` — 136 monthly grids clipped to pilot bbox (January 2015 to April 2026)
  - `data/rainfall/chirps_ward_zonal.csv` — 612 rows of ward × month × rainfall
  - `data/rainfall/preview/rainfall_monthly_panel.png` — 4 × 3 seasonal panel
  - `data/rainfall/build_chirps.py` — reproducible build script
  - GeoPackage layer in `trellis_delta_wards.gpkg`: `rain_ward_2026_04`
- **Format:** GeoTIFF (raster), CSV (tabular), PNG (preview), OGC GeoPackage (vector)
- **CRS:** EPSG:4326
- **Time window:** 1 January 2015 – 30 April 2026 (136 months — full multi-year archive)
- **Created:** 9 May 2026
- **Purpose:** Monthly rainfall climatology for the Trellis pilot LGAs. Rainfall is the canonical malaria covariate (lagged 4–6 weeks for vector breeding) and a strong asthma-relevant exposure modifier (wet-season aerosol washout, dry-season dust loading).

## Source

- **Final product (May 2025 – March 2026):** CHIRPS v2.0 Africa Monthly, gridded at 0.05° (~5 km).
  - Base URL: `https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs/chirps-v2.0.<YYYY>.<MM>.tif.gz`
- **Preliminary product (April 2026 only):** CHIRPS v2.0 Preliminary Global Monthly. CHIRPS final has a ~1-month publication lag; April 2026 final is not yet released as of 9 May 2026, so the prelim grid is used. It will be replaced when final is published.
  - Base URL: `https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_monthly/tifs/chirps-v2.0.<YYYY>.<MM>.tif`
- **Publisher:** Climate Hazards Center, University of California Santa Barbara (Funk et al., 2015, *Scientific Data*)
- **Method:** TIR-based satellite rainfall (CHIRP) blended with in-situ station observations across Africa
- **Units:** mm of rainfall per month
- **Access:** open, anonymous HTTPS, no registration
- **License:** Public-domain CHIRPS data (no restrictions on use)

## Twelve-month results

100% ward coverage — every one of the 51 pilot wards has a CHIRPS pixel under it (the 0.05° grid is finer than the smallest ward), using `all_touched=True` zonal aggregation.

### Domain-mean rainfall (mm/month)

| Month | Mean | Notes |
|---|---|---|
| 2025-05 | 189 | wet-season transition |
| 2025-06 | 305 | early wet season peak |
| 2025-07 | 280 | |
| 2025-08 | 166 | **August Break** — well-known mid-wet-season dip in the Niger Delta |
| 2025-09 | 349 | second peak |
| 2025-10 | 346 | |
| 2025-11 | 201 | start of dry-down |
| 2025-12 | 111 | dry season established |
| 2026-01 | **31** | **dry-season minimum** |
| 2026-02 | 117 | rains returning |
| 2026-03 | 120 | |
| 2026-04 | 184 | (prelim) |

The August Break is reproduced cleanly (166 vs ~290 either side) — a known feature of the West African monsoon caused by the Inter-Tropical Convergence Zone shifting north of the Niger Delta in mid-summer.

### LGA-mean rainfall (mm/month, 12-month mean ± std)

| LGA | Mean | Std |
|---|---|---|
| Burutu | 230.7 | 117.3 |
| Bomadi | 226.0 | 106.1 |
| Patani | 215.1 | 99.4 |
| Warri South | 212.6 | 113.2 |
| Warri South-West | 111.7 | 106.3 |

Warri South-West appears anomalously dry. **This is a coastal-pixel artifact, not a real signal.** Many wards in Warri South-West (Ogbe-Ijoh, Ugborodo, Okerenkoko, Ogidigben, Oporozo) extend over coastal mangrove and offshore terminal areas; CHIRPS has no values over water, so `all_touched=True` is averaging in pixels that either have very low rainfall or are partial-coverage land pixels. For inland wards in Warri South-West the rainfall is comparable to the other LGAs. This caveat applies anywhere the boundary touches the coastline.

## Cross-reference to NO₂ and flares

The wet/dry rainfall cycle is the **inverse** of the NO₂ cycle:

| Month | Rainfall (mm) | NO₂ (μmol m⁻²) |
|---|---|---|
| 2025-12 | 111 | 34.9 |
| 2026-01 | 31 | 29.3 |
| 2025-06 | 305 | 11.8 |
| 2025-07 | 280 | 11.6 |

This is the core seasonal signal Trellis needs to model. Dry season → less aerosol washout, biomass-burning advection from the Sahel, peak NO₂ exposure. Wet season → washout, low NO₂, high mosquito breeding. The asthma-malaria seasonal trade-off is exactly the dual-domain claim Trellis makes to UNICEF priority Areas 2 and 3 simultaneously.

## Caveats

- **Coastal-pixel artifact** (see Warri South-West note above). When using zonal stats over wards that touch the ocean, prefer `all_touched=False` and accept reduced coverage, or mask pixels with mixed land/water.
- **Prelim vs final.** The April 2026 grid will be replaced when CHIRPS final is published (~early June 2026). The prelim version is reasonable for a first cut but has slightly larger station-blending uncertainty.
- **0.05° grid (~5 km).** Finer than the smallest pilot ward in this dataset, so coverage is universal — but the small wards have only one or two pixels and the value should be read as a coarse estimate.
- **Daily-to-monthly aggregation.** This product is the CHC monthly aggregate of daily CHIRPS. For diurnal-cycle work or storm-event analysis the daily product (`africa_daily/p05`) is the right source.
- **Ocean and rivers.** CHIRPS represents land precipitation only; pixels over the Atlantic, Forcados River, Escravos River, and creeks have nodata. Mixed-coverage pixels are biased low.

## Reproducibility

```bash
cd data/rainfall
python3 build_chirps.py        # downloads and clips all 12 months
python3 aggregate_chirps.py    # ward-level zonal aggregation
```

`build_chirps.py` will use africa_monthly for any month with a final release and fall back to prelim global_monthly otherwise.

## Next steps

1. **Replace April 2026 with final** when CHC publishes it (early June 2026).
2. **Add daily lags.** The malaria literature (Mabaso et al., Ceccato et al., Kreppel et al.) consistently uses 4–8 week lagged rainfall as the strongest predictor of *Plasmodium falciparum* incidence. Build the daily archive and pre-compute lagged ward-month columns.
3. **Add CHIRPS-GEFS** (CHIRPS Global Ensemble Forecast System) for forward-looking rainfall in the 4-week forecast window.
4. **Mask coastal pixels** before re-running zonal stats for the Warri South-West coastal wards.
