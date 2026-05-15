"""Build a monthly Sentinel-5P tropospheric NO2 baseline over the Trellis pilot bbox.

Pulls Cloud Optimized GeoTIFFs from the MEEO Sentinel-5P open S3 bucket
(s3://meeo-s5p, anonymously accessible), windowed to the pilot bbox,
applies the qa_value >= 0.75 filter (NO2 product user manual recommendation),
composites to a monthly mean, and computes zonal mean per ward.
"""
from __future__ import annotations
import os
import calendar
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
import numpy as np
import rasterio
from botocore import UNSIGNED
from botocore.config import Config
from rasterio.windows import from_bounds as window_from_bounds

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("AWS_REGION", "eu-central-1")

BUCKET = "meeo-s5p"
PILOT_BBOX = (5.1571, 5.0118, 6.2930, 5.8299)
QA_THRESHOLD = 0.75
ORBIT_HOUR_RANGE = (10, 13)

HERE = Path(__file__).parent
OUT_DIR = HERE / "no2"
OUT_DIR.mkdir(exist_ok=True)


def s3_client():
    return boto3.client("s3", config=Config(signature_version=UNSIGNED, region_name="eu-central-1"))


def list_no2_cogs(year, month):
    s3 = s3_client()
    pairs = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        prefix = f"COGT/OFFL/L2__NO2___/{year:04d}/{month:02d}/{day:02d}/"
        keys = []
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
            keys.extend(o["Key"] for o in page.get("Contents", []))
        no2_keys = [k for k in keys if k.endswith("_PRODUCT_nitrogendioxide_tropospheric_column_4326.tif")]
        for nk in no2_keys:
            fname = nk.split("/")[-1]
            try:
                hour = int(fname.split("_L2__NO2____")[1][9:11])
            except (IndexError, ValueError):
                continue
            if not (ORBIT_HOUR_RANGE[0] <= hour <= ORBIT_HOUR_RANGE[1]):
                continue
            qk = nk.replace(
                "_PRODUCT_nitrogendioxide_tropospheric_column_4326.tif",
                "_PRODUCT_qa_value_4326.tif",
            )
            if qk in keys:
                pairs.append((nk, qk))
    return pairs


def windowed_read(no2_key, qa_key):
    no2_url = f"/vsis3/{BUCKET}/{no2_key}"
    qa_url = f"/vsis3/{BUCKET}/{qa_key}"
    with rasterio.open(no2_url) as src:
        win = window_from_bounds(*PILOT_BBOX, src.transform)
        no2 = src.read(1, window=win)
        win_transform = src.window_transform(win)
        nodata = src.nodata
    with rasterio.open(qa_url) as src:
        win = window_from_bounds(*PILOT_BBOX, src.transform)
        qa = src.read(1, window=win)
    valid = np.isfinite(no2)
    if nodata is not None:
        valid &= no2 != nodata
    valid &= np.isfinite(qa) & (qa >= QA_THRESHOLD)
    if not valid.any():
        return None
    return no2, valid, win_transform


def monthly_composite(year, month):
    pairs = list_no2_cogs(year, month)
    print(f"  {year}-{month:02d}: {len(pairs)} candidate orbits ({ORBIT_HOUR_RANGE[0]}-{ORBIT_HOUR_RANGE[1]}h UTC)")
    accum = None
    count = None
    transform = None
    n_with_data = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(windowed_read, nk, qk) for nk, qk in pairs]
        for fut in as_completed(futures):
            try:
                result = fut.result()
            except Exception:
                continue
            if result is None:
                continue
            n_with_data += 1
            no2, mask, tr = result
            if accum is None:
                accum = np.zeros(no2.shape, dtype=np.float64)
                count = np.zeros(no2.shape, dtype=np.int32)
                transform = tr
            if no2.shape != accum.shape:
                continue
            accum[mask] += no2[mask]
            count[mask] += 1
    if accum is None or int(count.sum()) == 0:
        print(f"  {year}-{month:02d}: NO valid data")
        return None
    mean = np.where(count > 0, accum / np.maximum(count, 1), np.nan).astype(np.float32)
    out_path = OUT_DIR / f"no2_{year:04d}_{month:02d}.tif"
    profile = {
        "driver": "GTiff", "height": mean.shape[0], "width": mean.shape[1],
        "count": 1, "dtype": "float32", "crs": "EPSG:4326",
        "transform": transform, "nodata": float("nan"), "compress": "deflate",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mean, 1)
        dst.update_tags(
            source="Sentinel-5P L2 NO2 OFFL via meeo-s5p AWS Open Data",
            qa_threshold=str(QA_THRESHOLD),
            orbits_with_data=str(n_with_data),
            orbits_total=str(len(pairs)),
            units="mol/m^2",
            window_bbox_WSEN=",".join(str(x) for x in PILOT_BBOX),
        )
    print(f"  {year}-{month:02d}: data orbits {n_with_data}/{len(pairs)}, "
          f"mean={np.nanmean(mean):.3e} mol/m^2 -> {out_path.name}")
    return out_path


def aggregate_to_wards(months):
    import geopandas as gpd
    import pandas as pd
    import shutil
    from rasterstats import zonal_stats

    gpkg = HERE / "trellis_delta_wards.gpkg"
    pilot = gpd.read_file("/tmp/trellis_delta_wards.gpkg", layer="pilot_wards")
    rows = []
    for y, m in months:
        tif = OUT_DIR / f"no2_{y:04d}_{m:02d}.tif"
        if not tif.exists():
            continue
        stats = zonal_stats(pilot, str(tif), stats=["mean", "count"], nodata=float("nan"))
        for ward, st in zip(pilot.itertuples(), stats):
            rows.append({
                "wardname": ward.wardname,
                "lganame": ward.lganame,
                "year": y, "month": m,
                "no2_mean_mol_m2": st["mean"],
                "valid_pixels": st["count"],
            })
    df = pd.DataFrame(rows)
    csv = OUT_DIR / "no2_ward_zonal.csv"
    df.to_csv(csv, index=False)
    print(f"\n  Zonal table: {len(df)} rows -> {csv}")
    if months:
        y, m = months[-1]
        sub = df[(df.year == y) & (df.month == m)].set_index(["lganame", "wardname"])
        merged = pilot.set_index(["lganame", "wardname"]).join(
            sub[["no2_mean_mol_m2", "valid_pixels"]]).reset_index()
        tmp = "/tmp/trellis_delta_wards.gpkg"
        layer = f"no2_ward_{y:04d}_{m:02d}"
        merged.to_file(tmp, layer=layer, driver="GPKG")
        shutil.copy2(tmp, gpkg)
        print(f"  Added layer '{layer}' to {gpkg}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        months = []
        for arg in sys.argv[1:]:
            y, m = arg.split("-")
            months.append((int(y), int(m)))
    else:
        months = [(2026, 4)]
    for y, m in months:
        monthly_composite(y, m)
    aggregate_to_wards(months)
