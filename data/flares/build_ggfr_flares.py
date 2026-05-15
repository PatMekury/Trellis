"""Build per-ward gas-flare exposure layer for Trellis from World Bank GGFR data."""

from __future__ import annotations

import shutil
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

HERE = Path(__file__).parent
SRC_XLSX = HERE / "ggfr_flare_locations_2012_2024.xlsx"
GPKG = HERE.parent / "trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"


def load_nigeria_flares():
    df = pd.read_excel(SRC_XLSX)
    df.columns = [c.strip().replace("  ", " ") for c in df.columns]
    ng = df[df["Country"] == "Nigeria"].copy()
    ng["Year"] = ng["Year"].astype(int)
    return ng


def site_summary(ng):
    grp = ng.groupby(["Latitude", "Longitude"], as_index=False)
    summary = grp.agg(
        total_bcm_2012_2024=("bcm", "sum"),
        mean_bcm_per_active_year=("bcm", "mean"),
        n_years_active=("Year", "nunique"),
        first_year=("Year", "min"),
        last_year=("Year", "max"),
        last_bcm=("bcm", lambda s: s.iloc[s.values.argsort()[-1]] if len(s) else 0),
        field_name=("Field Name", lambda s: s.dropna().iloc[0] if len(s.dropna()) else None),
        operator=("Field Operator", lambda s: s.dropna().iloc[0] if len(s.dropna()) else None),
        location_type=("Location", lambda s: s.dropna().iloc[0] if len(s.dropna()) else None),
        field_type=("Field Type", lambda s: s.dropna().iloc[0] if len(s.dropna()) else None),
    )
    summary["geometry"] = [Point(xy) for xy in zip(summary.Longitude, summary.Latitude)]
    return gpd.GeoDataFrame(summary, geometry="geometry", crs="EPSG:4326")


def main():
    ng = load_nigeria_flares()
    print(f"Nigeria flare records 2012-2024: {len(ng)}")

    sites = site_summary(ng)
    print(f"Unique flare sites in Nigeria: {len(sites)}")

    delta_wards = gpd.read_file(TMP_GPKG, layer="delta_wards").to_crs("EPSG:4326")

    sites_in_delta = gpd.sjoin(
        sites, delta_wards[["wardname", "lganame", "geometry"]], how="inner", predicate="within"
    ).drop(columns=["index_right"])
    print(f"Flare sites within Delta State: {len(sites_in_delta)}")
    print(f"  cumulative BCM >= 0.01: {(sites_in_delta.total_bcm_2012_2024 >= 0.01).sum()}")
    print(f"  cumulative BCM >= 0.1:  {(sites_in_delta.total_bcm_2012_2024 >= 0.1).sum()}")

    ward_summary = (
        sites_in_delta.groupby(["lganame", "wardname"])
        .agg(
            n_flare_sites=("Latitude", "size"),
            total_bcm_13yr=("total_bcm_2012_2024", "sum"),
            max_site_bcm=("total_bcm_2012_2024", "max"),
            last_year_bcm=("last_bcm", "sum"),
            operators=("operator", lambda s: ", ".join(sorted(set(s.dropna())))),
        )
        .reset_index()
    )

    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    ward_polys = pilot.merge(ward_summary, on=["lganame", "wardname"], how="left")
    for col in ("n_flare_sites", "total_bcm_13yr", "max_site_bcm", "last_year_bcm"):
        ward_polys[col] = ward_polys[col].fillna(0)
    ward_polys["operators"] = ward_polys["operators"].fillna("")

    print(f"\nPilot wards with flares: {(ward_polys.n_flare_sites > 0).sum()} / {len(ward_polys)}")
    print("\nTop 10 pilot wards by 13-year cumulative BCM:")
    top = ward_polys.nlargest(10, "total_bcm_13yr")[
        ["lganame", "wardname", "n_flare_sites", "total_bcm_13yr", "max_site_bcm"]
    ]
    print(top.to_string(index=False))

    ward_summary.to_csv(HERE / "delta_ward_flare_summary.csv", index=False)

    tmp_sites = "/tmp/delta_flare_sites.gpkg"
    if Path(tmp_sites).exists():
        Path(tmp_sites).unlink()
    sites_in_delta.to_file(tmp_sites, driver="GPKG")
    shutil.copy2(tmp_sites, HERE / "delta_flare_sites.gpkg")

    sites_in_delta.to_file(TMP_GPKG, layer="delta_flare_sites", driver="GPKG")
    ward_polys.to_file(TMP_GPKG, layer="ward_flare_summary", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"\nWrote layers to {GPKG}: delta_flare_sites, ward_flare_summary")


if __name__ == "__main__":
    main()
