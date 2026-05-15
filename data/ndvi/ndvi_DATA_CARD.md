# Data card: Sentinel-2 NDVI baseline (partial)

## Identity

- **Files:**
  - `data/ndvi/ndvi_annual_2025_2026.tif` — annual median NDVI composite, ~200 m grid
  - `data/ndvi/ndvi_2025_05.tif`, `ndvi_2025_06.tif`, `ndvi_2026_04.tif` — three monthly composites
  - `data/ndvi/ward_ndvi_annual.csv` — per-ward annual NDVI
  - `data/ndvi/ward_ndvi_monthly.csv` — per-ward × month NDVI for the three months that have a composite
  - `data/ndvi/build_ndvi.py` — monthly composite script
  - `data/ndvi/build_ndvi_annual.py` — annual composite script
  - GeoPackage layer `ward_ndvi` in `trellis_delta_wards.gpkg`
- **Format:** GeoTIFF (raster), CSV (tabular), GeoPackage (vector)
- **CRS:** EPSG:4326
- **Reference window:** May 2025 – April 2026 (annual); selected months for monthly composites
- **Created:** 9 May 2026
- **Purpose:** Vegetation-greenness baseline; in trellis.md predictor schema, this serves as the standing-water proxy (low NDVI = water/wet bare ground) and a vegetation-health control.

## Source

- **Dataset:** Sentinel-2 L2A surface reflectance via Earth Search STAC (Element 84 mirror)
- **Bucket:** `sentinel-cogs.s3.us-west-2.amazonaws.com` (anonymous AWS Open Data)
- **STAC API:** `https://earth-search.aws.element84.com/v1/search`
- **Bands used:** B04 (red, 665 nm) and B08 (NIR, 842 nm), both at 10 m native resolution
- **NDVI:** `(NIR − Red) / (NIR + Red)`, range [-1, +1], dimensionless
- **Cloud filter:** scene-level `eo:cloud_cover < 30%` for the annual composite
- **Access:** open, anonymous; no Earthdata or Copernicus credentials required
- **License:** Copernicus open access policy

## Method

For each scene that intersects the pilot bbox:

1. Read B04 and B08 as windowed reads in the source UTM CRS (10 m).
2. Reproject to a common 200 m grid in EPSG:4326 covering the pilot bbox.
3. Compute NDVI per pixel; mask `red ≤ 0` and `NIR ≤ 0` (atmospheric-correction failures).
4. Stack scenes; take per-pixel median to suppress residual cloud and shadow.

Annual composite uses the four cleanest scenes (lowest cloud cover) across the May 2025 to April 2026 window, plus opportunistic re-sampling to add tile coverage. Monthly composites pull up to four scenes per month with the same pipeline.

## Coverage — partial

This is the only predictor in the Trellis stack with materially incomplete coverage at the end of this session.

### Spatial coverage

- **Annual composite valid pixels:** 65,224 of 232,312 (~28%)
- **Pilot wards with at least one valid annual pixel:** 22 of 51 (43%)
- **LGA-level annual NDVI coverage:**

| LGA | Wards covered | Annual NDVI mean |
|---|---|---|
| Warri South | most | 0.58 |
| Warri South-West | partial | -0.02 |
| Burutu | partial | 0.14 |
| Bomadi | none | n/a |
| Patani | none | n/a |

### Temporal coverage

- **Monthly composites:** May 2025, June 2025, April 2026 (3 of 12 months)
- **Other months:** missing because the wet-season cloud cover (June through September) reduced the pool of usable Sentinel-2 scenes below the pipeline's minimum, and the per-month windowed-read budget exceeded the sandbox shell time limit.

### Why coverage is uneven

The Niger Delta is split across four Sentinel-2 MGRS tiles (31NGF, 31NHF, 32NKL, 32NKM). The cleanest scenes in the May 2025 – April 2026 window are concentrated on tile 31NGF (covering Warri South and Warri South-West) and 32NKM (covering far-eastern Burutu only). Tile 31NHF, which covers Bomadi and Patani, has poor cloud-free coverage in the dry months that survived the filter, and the bandwidth-constrained sandbox could not pull and reproject enough 31NHF scenes to fill in.

This is a *bandwidth and time* limit, not a *data availability* limit. The underlying data exists; a production-environment pull would have all four tiles' top scenes within minutes.

## Path to complete coverage

Three real options for closing the NDVI gap:

1. **Sentinel-1 SAR-derived RVI (Radar Vegetation Index).** Sentinel-1 sees through clouds. RVI is computed from VV and VH backscatter. Same Earth Search STAC, same anonymous AWS bucket. The right wet-season fallback for the Niger Delta and the standard practice in the EPIDEMIA-style malaria-modelling literature.
2. **Google Earth Engine.** GEE has both Sentinel-2 L2A and a built-in cloud-mask product (s2cloudless). A 12-month median composite for the Delta pilot domain takes one line of GEE Python and runs in seconds. Requires a free GEE account.
3. **Sentinel Hub Statistical API.** Returns per-polygon NDVI time series directly, with cloud masking applied server-side. Free tier (~30k requests/month). Trivial to script once a Sentinel Hub account is in place.

Either of options 2 or 3 is the right operational path; option 1 is the right cloud-resilient fallback. Trellis production will use one of these, with the partial Sentinel-2 composite kept as a sanity-check reference.

## Predictor table integration

Two columns added to `data/predictors/trellis_ward_month_predictors.csv`:

| Column | Source | Description |
|---|---|---|
| `ndvi_annual` | this dataset | Static annual NDVI for the ward, broadcast across all 12 months |
| `ndvi_monthly` | this dataset | Monthly NDVI where a composite exists (May 2025, June 2025, April 2026); NaN otherwise |
| `ndvi` | derived | Monthly value if available, else annual, else NaN |
| `ndvi_source` | derived | "monthly" or "annual" |

**Combined coverage in the predictor table:** 268 of 612 ward-months (43.8%). For a production model, this column will be filled either by SAR-derived RVI or by a complete Sentinel-2 composite from one of the auth-required services listed above; the current values are placeholders that demonstrate the join works and that the wards that *do* have data show the expected pattern (Warri South high vegetation, Warri South-West coastal-mangrove low, Burutu mid-range).

## Caveats

- **NDVI sign issues at coastal wards.** Warri South-West has a negative annual mean NDVI (-0.02) — that's water and very wet mangrove pixels driving the LGA mean. Real, but for malaria modelling the sign should be interpreted as "open water present" rather than "no vegetation."
- **Median composite hides change.** A median annual NDVI composite is a baseline; it cannot detect deforestation, land-use change, or seasonal vegetation pulses. Those need either monthly composites or a phenology metric (NDVI amplitude / phase).
- **200 m output grid.** Coarser than the 10 m native resolution. Adequate for ward-level zonal stats, not for sub-ward phenomena (a single tree, a single pond).
- **No SCL cloud mask.** The pipeline relies on scene-level cloud cover filtering and per-pixel `red > 0 & NIR > 0` masking. Adding the SCL band slowed the pipeline to the point of timing out in the sandbox. Production code should re-enable SCL masking.

## Reproducibility

```bash
cd data/ndvi
# Annual composite
python3 build_ndvi_annual.py
# Specific monthly composites (slow if cloudy)
python3 build_ndvi.py 2026-04
```

## Status against trellis.md

This is the **sixth** of the eight predictors. With this in (even partial), only DHIS2 historical health outcomes remains on the predictor list — and that one explicitly requires a future state-level data-sharing arrangement.

Predictor stack as of this session's end:

| # | Predictor | Status |
|---|---|---|
| 1 | NO₂ | Done — 12 months × 51 wards × 76.5% coverage |
| 2 | Rainfall | Done — 12 months × 51 wards × 100% |
| 3 | Flare exposure | Done — 13 years × 8 of 51 pilot wards |
| 4 | Health facilities | Done — static per-ward × 100% |
| 5 | Temperature | Done — daily × 51 wards × 100% |
| 6 | NDVI | **Partial** — annual + 3 monthly × 43.8% combined |
| 7 | Population | Done — static per-ward × 96.1% |
| 8 | DHIS2 health outcomes | Pending — partnership-dependent |
