# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path

ROOT_DIR = _Path(__file__).resolve().parent.parent.parent
"""Build the unified ward x month predictor table (v3: + population)."""
from __future__ import annotations

import shutil

import geopandas as gpd
import pandas as pd

DATA = ROOT_DIR / "data"
OUT = DATA / "predictors"
OUT.mkdir(exist_ok=True)
GPKG = DATA / "trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"


def main():
    no2 = pd.read_csv(DATA / "no2/no2_ward_zonal.csv")
    rain = pd.read_csv(DATA / "rainfall/chirps_ward_zonal.csv")
    temp = pd.read_csv(DATA / "temperature/ward_temperature_monthly.csv")
    flares = pd.read_csv(DATA / "flares/delta_ward_flare_summary.csv")
    fac = pd.read_csv(DATA / "health/delta_ward_facility_summary.csv")
    pop = pd.read_csv(DATA / "population/delta_ward_population.csv")

    no2_clean = no2.rename(
        columns={
            "no2_mean_mol_m2": "no2_mol_m2",
            "valid_pixels": "no2_valid_pixels",
        }
    )[["lganame", "wardname", "year", "month", "no2_mol_m2", "no2_valid_pixels"]]
    rain_clean = rain.rename(
        columns={
            "rain_mm": "rainfall_mm",
            "valid_pixels": "rainfall_valid_pixels",
        }
    )[["lganame", "wardname", "year", "month", "rainfall_mm", "rainfall_valid_pixels"]]
    temp_clean = temp[
        ["lganame", "wardname", "year", "month", "t2m_mean", "t2m_max", "t2m_min", "ts_mean", "n_days"]
    ]
    temp_clean = temp_clean.rename(columns={"n_days": "temp_n_days"})

    base = no2_clean.merge(rain_clean, on=["lganame", "wardname", "year", "month"], how="outer")
    base = base.merge(temp_clean, on=["lganame", "wardname", "year", "month"], how="outer")

    flares_clean = flares.rename(
        columns={
            "n_flare_sites": "flare_n_sites",
            "total_bcm_13yr": "flare_total_bcm_13yr",
            "max_site_bcm": "flare_max_site_bcm",
            "last_year_bcm": "flare_last_year_bcm",
            "operators": "flare_operators",
        }
    )[
        [
            "lganame",
            "wardname",
            "flare_n_sites",
            "flare_total_bcm_13yr",
            "flare_max_site_bcm",
            "flare_last_year_bcm",
            "flare_operators",
        ]
    ]
    fac_clean = fac.rename(
        columns={
            "n_facilities": "fac_total",
            "n_phc": "fac_phc",
            "n_secondary": "fac_secondary",
            "n_tertiary": "fac_tertiary",
            "n_public": "fac_public",
            "n_private": "fac_private",
        }
    )[
        [
            "lganame",
            "wardname",
            "fac_total",
            "fac_phc",
            "fac_secondary",
            "fac_tertiary",
            "fac_public",
            "fac_private",
        ]
    ]
    pop_clean = pop[["lganame", "wardname", "pop_total", "pop_under5"]]

    out = base.merge(flares_clean, on=["lganame", "wardname"], how="left")
    out = out.merge(fac_clean, on=["lganame", "wardname"], how="left")
    out = out.merge(pop_clean, on=["lganame", "wardname"], how="left")

    static_int = [
        "flare_n_sites",
        "fac_total",
        "fac_phc",
        "fac_secondary",
        "fac_tertiary",
        "fac_public",
        "fac_private",
        "pop_total",
        "pop_under5",
    ]
    static_float = ["flare_total_bcm_13yr", "flare_max_site_bcm", "flare_last_year_bcm"]
    for c in static_int:
        out[c] = out[c].fillna(0).astype(int)
    for c in static_float:
        out[c] = out[c].fillna(0.0)
    out["flare_operators"] = out["flare_operators"].fillna("")

    # Derived per-capita columns
    out["fac_per_1k_pop"] = (out["fac_total"] / out["pop_total"].replace(0, float("nan")) * 1000).round(2)
    out["phc_per_1k_u5"] = (out["fac_phc"] / out["pop_under5"].replace(0, float("nan")) * 1000).round(2)
    out["fac_per_1k_pop"] = out["fac_per_1k_pop"].fillna(0)
    out["phc_per_1k_u5"] = out["phc_per_1k_u5"].fillna(0)

    out["no2_umol_m2"] = out["no2_mol_m2"] * 1e6
    out["ym"] = out.apply(lambda r: f"{int(r.year):04d}-{int(r.month):02d}", axis=1)
    out = out.sort_values(["lganame", "wardname", "year", "month"]).reset_index(drop=True)

    cols = [
        "lganame",
        "wardname",
        "ym",
        "year",
        "month",
        "no2_mol_m2",
        "no2_umol_m2",
        "no2_valid_pixels",
        "rainfall_mm",
        "rainfall_valid_pixels",
        "t2m_mean",
        "t2m_max",
        "t2m_min",
        "ts_mean",
        "temp_n_days",
        "flare_n_sites",
        "flare_total_bcm_13yr",
        "flare_max_site_bcm",
        "flare_last_year_bcm",
        "flare_operators",
        "fac_total",
        "fac_phc",
        "fac_secondary",
        "fac_tertiary",
        "fac_public",
        "fac_private",
        "pop_total",
        "pop_under5",
        "fac_per_1k_pop",
        "phc_per_1k_u5",
    ]
    out = out[cols]

    # Reapply lags
    out["t"] = out["year"] * 12 + out["month"]
    for col in ["rainfall_mm", "t2m_mean"]:
        for lag, suf in [(1, "1m"), (2, "2m"), (3, "3m")]:
            out[f"{col}_lag{suf}"] = out.groupby(["lganame", "wardname"])[col].shift(lag)
    out = out.drop(columns=["t"])

    csv_path = OUT / "trellis_ward_month_predictors.csv"
    out.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path}: {len(out)} rows x {len(out.columns)} columns")

    # Coverage report
    print("\nWard-month coverage:")
    print(
        f"  NO2:                  {out.no2_mol_m2.notna().sum()} ({out.no2_mol_m2.notna().mean() * 100:.1f}%)"
    )
    print(
        f"  rainfall:             {out.rainfall_mm.notna().sum()} ({out.rainfall_mm.notna().mean() * 100:.1f}%)"
    )
    print(f"  temperature:          {out.t2m_mean.notna().sum()} ({out.t2m_mean.notna().mean() * 100:.1f}%)")
    print(f"  population (>=1):     {(out.pop_total > 0).sum()} ({(out.pop_total > 0).mean() * 100:.1f}%)")
    print(
        f"  flares (>=1):         {(out.flare_n_sites > 0).sum()} ({(out.flare_n_sites > 0).mean() * 100:.1f}%)"
    )
    print(f"  facilities (>=1):     {(out.fac_total > 0).sum()} ({(out.fac_total > 0).mean() * 100:.1f}%)")
    print(
        f"  rainfall lag1m:       {out.rainfall_mm_lag1m.notna().sum()} ({out.rainfall_mm_lag1m.notna().mean() * 100:.1f}%)"
    )
    print(
        f"  rainfall lag3m:       {out.rainfall_mm_lag3m.notna().sum()} ({out.rainfall_mm_lag3m.notna().mean() * 100:.1f}%)"
    )

    # Latest month polygon layer
    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    latest = out[(out.year == 2026) & (out.month == 4)]
    latest_static = latest.set_index(["lganame", "wardname"])
    merged = (
        pilot.set_index(["lganame", "wardname"])
        .join(latest_static.drop(columns=["ym", "year", "month"], errors="ignore"))
        .reset_index()
    )
    merged.to_file(TMP_GPKG, layer="predictors_ward_month_2026_04", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"\nUpdated layer 'predictors_ward_month_2026_04' in {GPKG}")


if __name__ == "__main__":
    main()
