
# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent
"""Pull CHIRPS Africa monthly rainfall from 2015-01 to 2026-04 (final + prelim April 2026)."""
import os, gzip, shutil, calendar
from urllib.request import urlretrieve
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import from_bounds as wfb

PILOT_BBOX = (5.1571, 5.0118, 6.2930, 5.8299)
HERE = (ROOT_DIR / "data/rainfall")
HERE.mkdir(exist_ok=True)
FINAL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs"
PRELIM = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_monthly/tifs"

def fetch(year, month):
    out = HERE / f"chirps_{year:04d}_{month:02d}.tif"
    if out.exists() and out.stat().st_size > 1000:
        return "exists"
    final_url = f"{FINAL}/chirps-v2.0.{year:04d}.{month:02d}.tif.gz"
    prelim_url = f"{PRELIM}/chirps-v2.0.{year:04d}.{month:02d}.tif"
    tmp_gz = Path(f"/tmp/chirps_{year:04d}_{month:02d}.tif.gz")
    tmp_full = Path(f"/tmp/chirps_{year:04d}_{month:02d}_full.tif")
    src_tag = "final"
    try:
        urlretrieve(final_url, tmp_gz)
        if tmp_gz.stat().st_size < 1000: raise OSError("too small")
        with gzip.open(tmp_gz, "rb") as fin, open(tmp_full, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    except Exception:
        try:
            urlretrieve(prelim_url, tmp_full)
            if tmp_full.stat().st_size < 1000: return "miss"
            src_tag = "prelim"
        except Exception:
            return "miss"
    with rasterio.open(tmp_full) as src:
        win = wfb(PILOT_BBOX[0]-0.1, PILOT_BBOX[1]-0.1, PILOT_BBOX[2]+0.1, PILOT_BBOX[3]+0.1, src.transform)
        arr = src.read(1, window=win)
        wt = src.window_transform(win)
        nd = src.nodata
    profile = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                   dtype=arr.dtype, crs="EPSG:4326", transform=wt,
                   nodata=nd if nd is not None else -9999, compress="deflate")
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(source_stream=src_tag, units="mm/month")
    return "ok"

years = list(range(2015, 2027))
done = miss = exists = 0
for y in years:
    end_m = 4 if y == 2026 else 12
    start_m = 1
    for m in range(start_m, end_m + 1):
        r = fetch(y, m)
        if r == "ok": done += 1
        elif r == "exists": exists += 1
        elif r == "miss": miss += 1
print(f"chirps multi-year: ok={done}, already existed={exists}, missing={miss}")
print(f"Total monthly TIFs in dir: {len(list(HERE.glob('chirps_*.tif')))}")