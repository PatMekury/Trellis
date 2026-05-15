"""Build a single 12-month annual NDVI median composite over the pilot bbox.

Strategy: query the entire 12-month window, sort by cloud cover ascending,
take the top-K cleanest scenes, median composite. This is a static layer
that gets broadcast across all months in the predictor table.
"""
import os, json
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

PILOT_BBOX = (5.1571, 5.0118, 6.2930, 5.8299)
HERE = (ROOT_DIR / "data/ndvi")
HERE.mkdir(exist_ok=True)
STAC = "https://earth-search.aws.element84.com/v1/search"
W,S,E,N = PILOT_BBOX
OUT_RES = 0.002  # ~200m output grid - coarser, faster
OUT_W = int(round((E-W)/OUT_RES))
OUT_H = int(round((N-S)/OUT_RES))
OUT_T = transform_from_bounds(W,S,E,N,OUT_W,OUT_H)


def search_year(start_year, start_month, end_year, end_month, max_scenes=10):
    last = 28 if end_month==2 else 30 if end_month in (4,6,9,11) else 31
    params = {
        "collections": "sentinel-2-l2a",
        "bbox": f"{W},{S},{E},{N}",
        "datetime": f"{start_year:04d}-{start_month:02d}-01T00:00:00Z/{end_year:04d}-{end_month:02d}-{last}T23:59:59Z",
        "limit": 200,
        "query": json.dumps({"eo:cloud_cover": {"lt": 30}}),
    }
    r = requests.get(STAC, params=params, timeout=30)
    r.raise_for_status()
    feats = r.json().get("features", [])
    feats.sort(key=lambda f: f.get("properties",{}).get("eo:cloud_cover", 100))
    return feats[:max_scenes]


def windowed_read(url, dtype="float32"):
    with rasterio.open(url) as src:
        sw,ss,se,sn = transform_bounds("EPSG:4326", src.crs, W,S,E,N, densify_pts=21)
        win = window_from_bounds(sw,ss,se,sn, src.transform).round_offsets().round_lengths()
        if win.width <= 0 or win.height <= 0: return None
        wt = src.window_transform(win)
        arr = src.read(1, window=win)
        dst = np.zeros((OUT_H, OUT_W), dtype=dtype)
        reproject(source=arr, destination=dst,
                  src_transform=wt, src_crs=src.crs,
                  dst_transform=OUT_T, dst_crs="EPSG:4326",
                  resampling=Resampling.nearest)
        return dst


def fetch_one(feat):
    a = feat["assets"]
    red = windowed_read(a["red"]["href"])
    nir = windowed_read(a["nir"]["href"])
    if red is None or nir is None: return None
    red = red.astype(np.float32); nir = nir.astype(np.float32)
    valid = (red > 0) & (nir > 0)
    denom = nir + red
    ndvi = np.full(red.shape, np.nan, dtype=np.float32)
    np.divide(nir-red, denom, out=ndvi, where=(denom > 0) & valid)
    # also drop unphysical NDVI > 1 or < -1
    ndvi[(ndvi < -1) | (ndvi > 1)] = np.nan
    return ndvi


def main():
    feats = search_year(2025, 5, 2026, 4, max_scenes=4)
    print(f"Selected {len(feats)} cleanest scenes across the year")
    for f in feats[:5]:
        p = f.get("properties", {})
        print(f"  {f['id']}  cloud={p.get('eo:cloud_cover',0):.0f}%  date={p.get('datetime','')[:10]}")

    stack = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fetch_one, f) for f in feats]
        for fut in as_completed(futures):
            try:
                a = fut.result()
                if a is not None and np.isfinite(a).any():
                    stack.append(a)
            except Exception as e:
                print(f"  read fail: {e}")

    if not stack:
        print("NO scenes contributed any valid pixel"); return

    median = np.nanmedian(np.stack(stack), axis=0).astype(np.float32)
    out = HERE / "ndvi_annual_2025_2026.tif"
    profile = dict(driver="GTiff", height=OUT_H, width=OUT_W, count=1,
                   dtype="float32", crs="EPSG:4326", transform=OUT_T,
                   nodata=float("nan"), compress="deflate")
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(median, 1)
        dst.update_tags(scenes_used=str(len(stack)), bbox_WSEN=",".join(str(x) for x in PILOT_BBOX),
                        time_window="2025-05-01 to 2026-04-30")
    valid = np.isfinite(median).sum()
    print(f"Wrote {out}: scenes={len(stack)}, valid={valid}/{median.size}, mean={np.nanmean(median):.3f}")


if __name__ == "__main__":
    main()