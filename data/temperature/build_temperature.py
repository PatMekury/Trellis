
# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent
"""Pull NASA POWER daily temperature for each pilot ward centroid; aggregate monthly."""
from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

HERE = (ROOT_DIR / "data/temperature")
HERE.mkdir(exist_ok=True)
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"

PARAMS = "T2M,T2M_MAX,T2M_MIN,TS"  # 2-m air temp; max/min; surface skin temp
START = "20250501"
END = "20260430"


def fetch_ward(args):
    lganame, wardname, lat, lon = args
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    r = requests.get(url, params={
        "parameters": PARAMS,
        "community": "RE",
        "latitude": lat,
        "longitude": lon,
        "start": START,
        "end": END,
        "format": "JSON",
    }, timeout=30)
    r.raise_for_status()
    d = r.json()
    params = d.get("properties", {}).get("parameter", {})
    rows = []
    if "T2M" in params:
        for ymd, t2m in params["T2M"].items():
            if t2m == -999:
                continue
            rows.append({
                "lganame": lganame, "wardname": wardname,
                "date": ymd,
                "t2m_c": t2m,
                "t2m_max_c": params.get("T2M_MAX", {}).get(ymd),
                "t2m_min_c": params.get("T2M_MIN", {}).get(ymd),
                "ts_c": params.get("TS", {}).get(ymd),
            })
    return rows


def main():
    # Use projected centroids to be precise
    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    pilot_proj = pilot.to_crs("EPSG:32632")  # UTM 32N covers Niger Delta
    centroids = pilot_proj.geometry.centroid.to_crs("EPSG:4326")
    pilot["centroid_lon"] = centroids.x
    pilot["centroid_lat"] = centroids.y

    args = [(r.lganame, r.wardname, r.centroid_lat, r.centroid_lon)
            for r in pilot.itertuples()]
    print(f"Fetching daily temperature for {len(args)} ward centroids...")

    all_rows = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_ward, a): a for a in args}
        done = 0
        for fut in as_completed(futures):
            try:
                rows = fut.result()
                all_rows.extend(rows)
            except Exception as e:
                a = futures[fut]
                print(f"  fail {a[0]}/{a[1]}: {e}")
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(args)} done ({time.time()-t0:.1f}s)")

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["year"] = df.date.dt.year
    df["month"] = df.date.dt.month
    print(f"\nDaily rows: {len(df)}  unique wards: {df[['lganame','wardname']].drop_duplicates().shape[0]}")

    # Save raw daily
    df.to_csv(HERE / "ward_temperature_daily.csv", index=False)

    # Aggregate to monthly per ward
    monthly = df.groupby(["lganame", "wardname", "year", "month"]).agg(
        t2m_mean=("t2m_c", "mean"),
        t2m_max=("t2m_max_c", "max"),
        t2m_min=("t2m_min_c", "min"),
        ts_mean=("ts_c", "mean"),
        n_days=("t2m_c", "size"),
    ).round(2).reset_index()
    monthly.to_csv(HERE / "ward_temperature_monthly.csv", index=False)
    print(f"Monthly rows: {len(monthly)}")
    print(f"\nT2M monthly summary by LGA (12-month mean):")
    print(monthly.groupby("lganame")["t2m_mean"].agg(["mean","std"]).round(2).to_string())
    print(f"\nMonthly T2M domain mean by year-month:")
    monthly["ym"] = monthly.apply(lambda r: f"{int(r.year)}-{int(r.month):02d}", axis=1)
    print(monthly.groupby("ym")["t2m_mean"].mean().round(2).to_string())


if __name__ == "__main__":
    main()