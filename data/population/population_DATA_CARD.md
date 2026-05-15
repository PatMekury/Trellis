# Data card: WorldPop population baseline

## Identity

- **Files:**
  - `data/population/nga_pop_2024_1km.tif` — Nigeria 2024 constrained 1km population raster (4.2 MB)
  - `data/population/delta_ward_population.csv` — per-ward total and under-5 estimates (267 Delta wards)
  - `data/population/build_population.py` — reproducible build script
  - GeoPackage layer in `trellis_delta_wards.gpkg`: `ward_population` (51 pilot wards joined to population)
- **Format:** GeoTIFF (raster), CSV (tabular), GeoPackage (vector)
- **CRS:** EPSG:4326
- **Reference year:** 2024
- **Created:** 9 May 2026
- **Purpose:** Population denominator for the Trellis pilot domain. Enables per-capita facility ratios, child-population-weighted exposure metrics, and equity-driven sensor-siting prioritisation.

## Source

- **Dataset:** WorldPop Global 2015–2030, R2025A release, 1 km constrained UA (Urban-Aware) for Nigeria, year 2024
- **File pulled:** `nga_pop_2024_CN_1km_R2025A_UA_v1.tif`
- **URL:** `https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2024/NGA/v1/1km_ua/constrained/nga_pop_2024_CN_1km_R2025A_UA_v1.tif`
- **Publisher:** WorldPop Research Group, University of Southampton
- **Method:** Random Forest dasymetric mapping with built-area covariates, calibrated against the most recent national census + projection. The "constrained" variant restricts population to identified built-up pixels. The "UA" (Urban-Aware) variant applies an urban-rural disaggregation refinement.
- **Native resolution:** 30 arc-seconds (~1 km at the equator). A 100 m version is also published (~150 MB) but the WorldPop server does not support HTTP range requests, so windowed reads are not possible from the sandbox; the 1 km product is the practical anonymous-access option.
- **Access:** open, anonymous HTTPS; no registration
- **License:** Creative Commons Attribution 4.0 International (CC-BY 4.0)

## Method

Zonal sum (not mean — population must be summed) using `rasterstats.zonal_stats` over the `delta_wards` polygons. The 1 km resolution is finer than every Delta ward, so the sum is unbiased.

The `pop_under5` column is **derived**, not measured: `pop_total × 0.156`. The 0.156 factor is the UN World Population Prospects 2024 estimate of Nigeria's national share of population aged 0–4. This is a single-factor approximation that ignores known regional variation (northern states ~17–18%, southern states ~13–14%; Delta is southern). It will be replaced with WorldPop's age-sex-structure 100 m rasters (`nga_f_0_2020`, `nga_f_1_2020`, `nga_m_0_2020`, `nga_m_1_2020`) once a higher-bandwidth pull environment is available.

## Twelve-month results

The total population is static (no monthly variation), so this layer adds two static columns to every ward-month row in the predictor table.

### Domain totals

- **Delta State total population:** 6,549,243 (zonal sum across all 267 Delta wards)
- **Pilot LGA total:** 699,667 across 51 wards
- **Pilot under-5 estimate:** 109,149

### LGA-level summary

| LGA | Wards | Total pop | U5 pop | Median ward pop |
|---|---|---|---|---|
| Warri South | 10 | 332,671 | 51,895 | 27,565 |
| Burutu | 11 | 136,865 | 21,352 | 11,105 |
| Patani | 10 | 99,696 | 15,552 | 9,987 |
| Bomadi | 10 | 79,827 | 12,454 | 3,551 |
| Warri South-West | 10 | 50,608 | 7,896 | 3,097 |

The five-LGA character is now anchored numerically. Warri South is the urban centre with 1 in every 2 pilot residents; Warri South-West is the sparsest because most of its area is mangrove and offshore, with population concentrated in a few coastal villages.

### Top wards by population

| LGA | Ward | Total pop | Under-5 | NO₂ rank? | Facilities |
|---|---|---|---|---|---|
| Warri South | Ekurede | 78,506 | 12,247 | yes (#2 of 51) | 12 |
| Warri South | Ubeji | 66,118 | 10,314 | top-5 | 11 |
| Warri South | Okere | 59,337 | 9,257 | top-10 | 13 |
| Warri South | Igbudu | 49,836 | 7,774 | top-10 | 14 |
| Bomadi | Bomadi | 37,392 | 5,833 | n/a | 5 |

**Ekurede** continues to be the strongest single sensor candidate — second-highest NO₂, 12 health facilities, and 78,500 residents including 12,000 children under 5. A sensor-attached forecast that delivers an SMS to caregivers in Ekurede reaches one of the largest exposed child populations in the pilot domain.

### Wards with very low or zero population

| LGA | Ward | Total pop | Note |
|---|---|---|---|
| Bomadi | Akugbene 2 | 0 | Also zero facilities (flagged earlier) |
| Warri South | Bowen | 0 | Likely a coastal-pixel artefact; this ward is offshore |
| Warri South-West | Ajudaibo | 280 | Coastal mangrove |
| Warri South-West | Madangho | 538 | Coastal mangrove |
| Warri South-West | Akpakpa | 657 | Also zero facilities (flagged earlier) |

The two zero-population wards likely have small permanent populations not captured by the built-area covariates the WorldPop model uses. For Trellis purposes, treat them as low-population mangrove zones rather than truly empty — exposure is real, just sparse.

## Derived columns added to the predictor table

| Column | Formula | Description |
|---|---|---|
| `pop_total` | zonal sum | Total ward population |
| `pop_under5` | `pop_total × 0.156` | Under-5 estimate |
| `fac_per_1k_pop` | `fac_total / pop_total × 1000` | Facilities per 1,000 residents |
| `phc_per_1k_u5` | `fac_phc / pop_under5 × 1000` | PHCs per 1,000 children under 5 |

## Caveats

- **1 km resolution.** Smaller than every Delta ward, but coarser than the 100 m product. For the smallest pilot wards (~5 km²) this gives 5–10 contributing pixels — adequate for ward totals, less precise for sub-ward analysis.
- **Constrained variant.** This product zeroes out population in pixels with no detected built area. Where the built-area covariate misses small settlements (riverine clusters in mangrove), population is biased low. Trellis should cross-check against the National Population Commission ward-level enumeration once the partnership is in place.
- **Under-5 fraction is national, not local.** The 0.156 factor is honest about being a placeholder. A direct WorldPop AgeSex pull will refine it.
- **Reference year is 2024.** Nigeria's growth rate is ~2.4%/yr, so 2024 figures are ~3% low for "now". For a 2026 baseline this is acceptable; refresh annually.

## Reproducibility

```bash
cd data/population
curl -sL -o nga_pop_2024_1km.tif \
  "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2024/NGA/v1/1km_ua/constrained/nga_pop_2024_CN_1km_R2025A_UA_v1.tif"
python3 build_population.py
```

## Next steps

1. **Replace u5 estimate with direct WorldPop AgeSex.** Pull the four 100 m rasters from `Global_2000_2020/AgeSex_structures/2020/NGA/`, sum to under-5, zonal-sum to wards, growth-adjust to 2024.
2. **NPC ward-level enumeration.** Cross-check against the official National Population Commission projections at admin-3 once that data source becomes accessible to the project.
3. **Distance-to-facility.** With population grids and facility points, derive a population-weighted distance-to-nearest-facility for each ward. Identifies the wards where the average resident is far from any care point.
4. **Population-weighted exposure.** Multiply pop × NO₂ ward by ward to get total ward-level NO₂ dose. The ranking by total dose differs from the ranking by mean concentration and may be more relevant for advocacy.
