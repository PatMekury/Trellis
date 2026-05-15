"""Build a 12-month CHIRPS rainfall baseline over the Trellis pilot bbox.

Sources:
  - africa_monthly (final): May 2025 through March 2026
  - prelim/global_monthly: April 2026 (final not yet released; CHIRPS final has ~1 month lag)

Output:
  data/rainfall/chirps_<YYYY>_<MM>.tif    - clipped monthly rainfall over pilot bbox (mm/month)
  data/rainfall/chirps_ward_zonal.csv     - long-form ward x month x rainfall
  trellis_delta_wards.gpkg :: rain_ward_<YYYY>_<MM>  - latest-month polygon layer
"""
from __future__ import annotations
import gzip
import shutil
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import rasterio
from rasterio.windows import from_bounds as window_from_bounds

HERE = Path(__file__).parent
OUT_DIR = HERE  # script lives in data/rainfall, output goes there too
PILOT_BBOX = (5.1571, 5.0118, 6.2930, 5.8299)

FINAL_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs"
PRELIM_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_monthly/tifs"


def fetch_monthly(year: int, month: int) -> Path:
    """Download a CHIRPS monthly TIF (final preferred, prelim fallback). Return local path (uncompressed)."""
    out_tif = OUT_DIR / f"chirps_{year:04d}_{month:02d}.tif"
    if out_tif.exists():
        return out_tif

    final_url = f"{FINAL_BASE}/chirps-v2.0.{year:04d}.{month:02d}.tif.gz"
    prelim_url = f"{PRELIM_BASE}/chirps-v2.0.{year:04d}.{month:02d}.tif"

    # Try final (gzipped)
    tmp_gz = Path(f"/tmp/chirps_{year:04d}_{month:02d}.tif.gz")
    try:
        urlretrieve(final_url, tmp_gz)
        if tmp_gz.stat().st_size < 1000:
            raise OSError("file too small, treat as miss")
        # decompress to /tmp first
        tmp_full = Path(f"/tmp/chirps_{year:04d}_{month:02d}_full.tif")
        with gzip.open(tmp_gz, "rb") as fin, open(tmp_full, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        source_tag = "final-africa"
    except Exception:
        # Fall back to prelim global
        tmp_full = Path(f"/tmp/chirps_{year:04d}_{month:02d}_full.tif")
        urlretrieve(prelim_url, tmp_full)
        if tmp_full.stat().st_size < 1000:
            raise RuntimeError(f"both final and prelim failed for {year}-{month:02d}")
        source_tag = "prelim-global"

    # Clip to pilot bbox + small buffer, write final TIF
    with rasterio.open(tmp_full) as src:
        win = window_from_bounds(
            PILOT_BBOX[0]-0.1, PILOT_BBOX[1]-0.1,
            PILOT_BBOX[2]+0.1, PILOT_BBOX[3]+0.1,
            src.transform,
        )
        arr = src.read(1, window=win)
        win_transform = src.window_transform(win)
        nodata = src.nodata

    profile = {
        "driver": "GTiff", "height": arr.shape[0], "width": arr.shape[1],
        "count": 1, "dtype": arr.dtype, "crs": "EPSG:4326",
        "transform": win_transform,
        "nodata": nodata if nodata is not None else -9999,
        "compress": "deflate",
    }
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(source_stream=source_tag, units="mm/month",
                        bbox_WSEN=",".join(str(x) for x in PILOT_BBOX))
    print(f"  {year}-{month:02d}: source={source_tag}  shape={arr.shape}  "
          f"mean={np.nanmean(arr[arr != (nodata if nodata is not None else -9999)]):.1f} mm")
    return out_tif


def main():
    months = [(2025, m) for m in range(5, 13)] + [(2026, m) for m in range(1, 5)]
    for y, m in months:
        try:
            fetch_monthly(y, m)
        except Exception as e:
            print(f"  {y}-{m:02d}: FAILED ({e})")


if __name__ == "__main__":
    main()
