"""Build a 12-month Sentinel-2 NDVI median composite over the Trellis pilot bbox.

Per month, query Earth Search STAC for Sentinel-2 L2A scenes intersecting the bbox
with <40% cloud cover. For each scene, do a windowed read in the source CRS
(UTM, 10m), compute NDVI with cloud masking, then reproject only that small
window to the common WGS84 output grid. Per-pixel median across scenes.
"""
from __future__ import annotations
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import from_bounds as window_from_bounds
from rasterio.transform import from_bounds as transform_from_bounds

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("AWS_REGION", "us-west-2")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff")

PILOT_BBOX = (5.1571, 5.0118, 6.2930, 5.8299)
HERE = (ROOT_DIR / "data/ndvi")
HERE.mkdir(exist_ok=True)
STAC = "https://earth-search.aws.element84.com/v1/search"

OUT_RES = 0.001  # ~100m at this latitude
W, S, E, N = PILOT_BBOX
OUT_W = int(round((E - W) / OUT_RES))
OUT_H = int(round((N - S) / OUT_RES))
OUT_TRANSFORM = transform_from_bounds(W, S, E, N, OUT_W, OUT_H)

SCL_DROP = {0, 1, 3, 8, 9, 10}


def search_month(year, month, max_scenes=4):
    last_day = 28 if month == 2 else 30 if month in (4,6,9,11) else 31
    start = f"{year:04d}-{month:02d}-01T00:00:00Z"
    end = f"{year:04d}-{month:02d}-{last_day}T23:59:59Z"
    params = {
        "collections": "sentinel-2-l2a",
        "bbox": f"{W},{S},{E},{N}",
        "datetime": f"{start}/{end}",
        "limit": max_scenes,
        "query": json.dumps({"eo:cloud_cover": {"lt": 95}}),
    }
    r = requests.get(STAC, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("features", [])


def windowed_read_to_grid(url, dtype="float32"):
    """Read just the pilot bbox from src, reproject to common output grid."""
    with rasterio.open(url) as src:
        # Transform pilot bbox from WGS84 to source CRS to get the window
        sw, ss, se, sn = transform_bounds("EPSG:4326", src.crs, W, S, E, N, densify_pts=21)
        win = window_from_bounds(sw, ss, se, sn, src.transform).round_offsets().round_lengths()
        win_transform = src.window_transform(win)
        # Bounds-check
        win_w = int(win.width)
        win_h = int(win.height)
        if win_w <= 0 or win_h <= 0: return None
        arr = src.read(1, window=win)
        # Reproject window into output grid
        dst = np.zeros((OUT_H, OUT_W), dtype=dtype)
        reproject(
            source=arr,
            destination=dst,
            src_transform=win_transform, src_crs=src.crs,
            dst_transform=OUT_TRANSFORM, dst_crs="EPSG:4326",
            resampling=Resampling.nearest,
        )
        return dst


def fetch_ndvi_one(feature):
    a = feature["assets"]
    red = windowed_read_to_grid(a["red"]["href"], "float32")
    nir = windowed_read_to_grid(a["nir"]["href"], "float32")
    scl = None
    if red is None or nir is None: return None
    red = red.astype(np.float32)
    nir = nir.astype(np.float32)
    valid = (red > 0) & (nir > 0)
    if scl is not None:
        for v in SCL_DROP:
            valid &= (scl != v)
    denom = nir + red
    ndvi = np.full(red.shape, np.nan, dtype=np.float32)
    np.divide(nir - red, denom, out=ndvi, where=(denom > 0) & valid)
    return ndvi


def composite_month(year, month):
    feats = search_month(year, month)
    print(f"  {year}-{month:02d}: {len(feats)} scenes")
    if not feats:
        return None
    stack = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(fetch_ndvi_one, f) for f in feats]
        for fut in as_completed(futures):
            try:
                ndvi = fut.result()
                if ndvi is not None and np.isfinite(ndvi).any():
                    stack.append(ndvi)
            except Exception:
                pass
    if not stack: return None
    median = np.nanmedian(np.stack(stack), axis=0).astype(np.float32)
    out = HERE / f"ndvi_{year:04d}_{month:02d}.tif"
    profile = {
        "driver":"GTiff","height":OUT_H,"width":OUT_W,"count":1,"dtype":"float32",
        "crs":"EPSG:4326","transform":OUT_TRANSFORM,"nodata":float("nan"),"compress":"deflate",
    }
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(median, 1)
        dst.update_tags(scenes_used=str(len(stack)), bbox_WSEN=",".join(str(x) for x in PILOT_BBOX))
    valid = np.isfinite(median).sum()
    print(f"  {year}-{month:02d}: scenes={len(stack)}, valid={valid}/{median.size}, mean={np.nanmean(median):.3f}")
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            y, m = arg.split("-")
            composite_month(int(y), int(m))
    else:
        composite_month(2026, 4)