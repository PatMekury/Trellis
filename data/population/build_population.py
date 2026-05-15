"""Aggregate WorldPop 1km Nigeria 2024 to pilot ward total population.

Adds two columns to the ward profile:
  - pop_total: total population per ward (zonal sum from 1km raster)
  - pop_under5: estimated under-5 population, as 0.156 * pop_total (Nigeria national fraction)

The 0.156 multiplier is the UN World Population Prospects 2024 estimate of Nigeria's under-5
share of total population. Delta State, being southern, runs marginally lower (~0.14); this
single-factor approach is replaced by direct WorldPop AgeSex layers when 100m downloads are
feasible.
"""
from pathlib import Path
import shutil
import geopandas as gpd
import pandas as pd
import numpy as np
from rasterstats import zonal_stats

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DATA = (ROOT_DIR / "data")
POP = DATA / "population"
GPKG = DATA / "trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"

# UN World Population Prospects 2024: Nigeria u5 fraction
U5_FRACTION = 0.156

def main():
    pop_tif = POP / "nga_pop_2024_1km.tif"

    # Statewide ward sums
    delta_wards = gpd.read_file(TMP_GPKG, layer="delta_wards")
    stats = zonal_stats(delta_wards, str(pop_tif), stats=["sum","count"], nodata=-99999)
    delta_wards["pop_total"] = [round(s["sum"]) if s["sum"] else 0 for s in stats]
    delta_wards["pop_under5"] = (delta_wards["pop_total"] * U5_FRACTION).round().astype(int)
    delta_wards["pixel_count"] = [s["count"] for s in stats]
    print(f"Delta total pop (zonal sum across wards): {delta_wards['pop_total'].sum():,.0f}")

    # Pilot subset
    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    pilot_pop = pilot.merge(
        delta_wards[["lganame","wardname","pop_total","pop_under5","pixel_count"]],
        on=["lganame","wardname"], how="left"
    )
    print(f"\nPilot wards population: {pilot_pop['pop_total'].sum():,.0f}")
    print(f"Pilot wards under-5: {pilot_pop['pop_under5'].sum():,.0f}")

    print(f"\nLGA population summary:")
    lga_summary = pilot_pop.groupby("lganame").agg(
        wards=("wardname","size"),
        total_pop=("pop_total","sum"),
        u5_pop=("pop_under5","sum"),
        median_ward_pop=("pop_total","median"),
    )
    print(lga_summary.to_string())

    print(f"\nTop 5 pilot wards by population:")
    top = pilot_pop.nlargest(5, "pop_total")[["lganame","wardname","pop_total","pop_under5"]]
    print(top.to_string(index=False))

    print(f"\nBottom 5 pilot wards by population:")
    bot = pilot_pop.nsmallest(5, "pop_total")[["lganame","wardname","pop_total","pop_under5"]]
    print(bot.to_string(index=False))

    # Ward CSV
    out_csv = POP / "delta_ward_population.csv"
    delta_wards[["lganame","wardname","pop_total","pop_under5","pixel_count"]].to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}")

    # GeoPackage layer
    pilot_pop_clean = pilot_pop.drop(columns=["pixel_count"], errors="ignore")
    pilot_pop_clean.to_file(TMP_GPKG, layer="ward_population", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"Added layer 'ward_population' to {GPKG}")


if __name__ == "__main__":
    main()