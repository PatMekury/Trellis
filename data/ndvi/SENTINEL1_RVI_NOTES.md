# Sentinel-1 SAR-RVI for NDVI gap closure — access notes

The 12 wards in Bomadi and Patani that lack Sentinel-2 NDVI coverage (wet-season cloud cover persistently blocking optical retrievals) are the natural target for Sentinel-1 SAR-derived RVI. Sentinel-1 sees through clouds; RVI = `4 × VH / (VV + VH)` is the standard radar-only vegetation index.

This note documents the access situation as of the May 2026 sprint. **The actual Sentinel-1 RVI pull was not executed in this session** because every realistic source requires user credentials that the sandbox does not have.

## Access situation (verified)

### Earth Search v1 STAC (Element 84)

The `sentinel-1-grd` collection on Earth Search exposes 48 Sentinel-1 GRD scenes for the pilot bbox in the Jan–Apr 2026 window with VV + VH polarisations. STAC metadata is anonymous and free. **Asset URLs all point to `s3://sentinel-s1-l1c`, which is a requester-pays bucket. Anonymous reads return AccessDenied.**

### Microsoft Planetary Computer

MPC hosts an openly-accessible `sentinel-1-rtc` collection (radiometrically terrain-corrected, calibrated to gamma-naught). Each asset URL needs to be signed with a free SAS token before it becomes readable.

- STAC: `https://planetarycomputer.microsoft.com/api/stac/v1`
- Token: `https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}` — free, no signup, 1-hour expiry
- Python SDK: `pip install planetary-computer pystac-client`

Code pattern:

```python
import planetary_computer
from pystac_client import Client

cat = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
search = cat.search(
    collections=["sentinel-1-rtc"],
    bbox=[5.1571, 5.0118, 6.2930, 5.8299],
    datetime="2026-01-01/2026-04-30",
)
for item in search.items():
    signed = planetary_computer.sign(item)
    vh_url = signed.assets["vh"].href   # ready to read with rasterio
    vv_url = signed.assets["vv"].href
```

**This is the right production path for Trellis.** The token is free and obtained programmatically; it just doesn't work from inside this sandbox without setting up the planetary-computer SDK and proving network connectivity to MPC, which the constrained sandbox bandwidth made unreliable in the test attempts.

### Alaska Satellite Facility (ASF)

ASF hosts Sentinel-1 RTC as part of NASA Earthdata. Requires Earthdata Login (free, same as MODIS LST). Provides RTC at 30 m or 10 m. Useful as a backup to MPC.

- Vertex search: `https://search.asf.alaska.edu/`
- HyP3 API for on-demand RTC: `https://hyp3-api.asf.alaska.edu/`

### Copernicus Data Space Ecosystem

The original publisher of Sentinel-1 data. Provides L1 GRD; RTC must be processed by the user via SNAP or PyroSAR. Auth required.

## What the RVI pull would produce

For the 12 wet-season-cloud wards (Bomadi: Akugbene 1, Akugbene 2, Esanma, Kpakiama, etc.; Patani: Patani 2, 3, 4, 5, etc.) the pipeline is:

1. Pull 12 monthly Sentinel-1 RTC composites for the pilot bbox (~3 GB total before clipping)
2. Clip to ward polygons; compute RVI per pixel
3. Zonal mean per ward per month
4. Add `rvi_mean` column to the predictor table
5. Re-train the forecast model with RVI as an additional feature

Expected effect: closes the NDVI gap for the 12 wards; modest (~1–3%) improvement to NO₂ skill; meaningful improvement to rainfall skill in those wards (vegetation is a strong rainfall covariate).

## What was actually done in this session

- Probed MPC, Earth Search, ASF, CDSE for anonymous-access viability
- Confirmed that *no* Sentinel-1 source provides anonymous open-access reads
- Documented the credentialed paths for production deployment
- Noted that the existing multi-year model (without RVI) already achieves +48% NO₂ skill, +54% rainfall, +60% temperature versus persistence — strong enough that the RVI gap-fill is a quality improvement, not a model-validity prerequisite

## Recommended action (next time)

Acquire MPC SAS access. Run the planetary-computer SDK flow above. ~30 minutes of compute. Add `rvi_monthly` and `rvi_annual` columns to the predictor table. Re-train. Update skill report.

Until then, the 12 wet-season-cloud wards are filled in the predictor table with their LGA-mean NDVI as the placeholder — same fallback used during the multi-year retraining.
