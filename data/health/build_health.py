# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path

ROOT_DIR = _Path(__file__).resolve().parent.parent.parent
"""Build Trellis health-facility and LGA layers from GRID3 v2.0."""
from __future__ import annotations

import shutil
from pathlib import Path

import geopandas as gpd

HERE = ROOT_DIR / "data/health"
GPKG = ROOT_DIR / "data/trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"


def main():
    # LGAs
    lgas = gpd.read_file(HERE / "delta_lgas.geojson")
    lgas = lgas.rename(columns=str.lower)
    for c in ("fid", "globalid", "shape__area", "shape__length"):
        if c in lgas.columns:
            lgas = lgas.drop(columns=c)
    print(f"Delta LGAs: {len(lgas)}")

    # Health facilities — fields are lowercase already
    hf = gpd.read_file(HERE / "delta_facilities.geojson")
    hf = hf.rename(columns={"state": "statename", "lga": "lganame", "ward": "wardname"})
    print(f"Delta health facilities: {len(hf)}")
    print(f"  ownership types: {hf['ownership'].value_counts().to_dict()}")
    print(f"  facility levels: {hf['facility_level'].value_counts().to_dict()}")

    # Per-ward facility counts via spatial join to delta_wards
    wards = gpd.read_file(TMP_GPKG, layer="delta_wards").to_crs("EPSG:4326")
    hf_in_ward = gpd.sjoin(
        hf,
        wards[["wardname", "lganame", "geometry"]],
        how="left",
        predicate="within",
        lsuffix="hf",
        rsuffix="ward",
    )

    # Use the ward-from-spatial-join, falling back to GRID3-attributed ward when join misses
    hf_in_ward["wardname_final"] = hf_in_ward["wardname_ward"].fillna(hf_in_ward["wardname_hf"])
    hf_in_ward["lganame_final"] = hf_in_ward["lganame_ward"].fillna(hf_in_ward["lganame_hf"])
    matched = hf_in_ward["wardname_ward"].notna().sum()
    print(f"  facilities matched to a ward polygon: {matched}/{len(hf_in_ward)}")

    summary = (
        hf_in_ward.groupby(["lganame_final", "wardname_final"])
        .agg(
            n_facilities=("facility_name", "size"),
            n_phc=("facility_level", lambda s: (s.str.contains("Primary", case=False, na=False)).sum()),
            n_secondary=(
                "facility_level",
                lambda s: (s.str.contains("Secondary", case=False, na=False)).sum(),
            ),
            n_tertiary=("facility_level", lambda s: (s.str.contains("Tertiary", case=False, na=False)).sum()),
            n_public=("ownership", lambda s: (s.str.lower() == "public").sum()),
            n_private=("ownership", lambda s: (s.str.lower() == "private").sum()),
        )
        .reset_index()
        .rename(columns={"lganame_final": "lganame", "wardname_final": "wardname"})
    )

    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    pilot_summary = pilot.merge(summary, on=["lganame", "wardname"], how="left")
    for c in ("n_facilities", "n_phc", "n_secondary", "n_tertiary", "n_public", "n_private"):
        pilot_summary[c] = pilot_summary[c].fillna(0).astype(int)

    print(
        f"\nPilot wards with at least one facility: {(pilot_summary.n_facilities > 0).sum()} / {len(pilot_summary)}"
    )
    no_fac = pilot_summary[pilot_summary.n_facilities == 0][["lganame", "wardname"]]
    if len(no_fac):
        print(f"\nPilot wards with ZERO facilities ({len(no_fac)}):")
        print(no_fac.to_string(index=False))

    print("\nPilot wards by facility count, top 5:")
    print(
        pilot_summary.nlargest(5, "n_facilities")[
            ["lganame", "wardname", "n_facilities", "n_phc", "n_public", "n_private"]
        ].to_string(index=False)
    )

    # Write outputs
    summary.to_csv(HERE / "delta_ward_facility_summary.csv", index=False)

    # Standalone GPKGs
    for name, gdf in [("delta_lgas", lgas), ("delta_health_facilities", hf)]:
        tmp = f"/tmp/{name}.gpkg"
        if Path(tmp).exists():
            Path(tmp).unlink()
        gdf.to_file(tmp, driver="GPKG")
        shutil.copy2(tmp, HERE / f"{name}.gpkg")

    # Append layers to main GeoPackage
    lgas.to_file(TMP_GPKG, layer="delta_lgas", driver="GPKG")
    hf_clean = hf.drop(columns=["index_hf", "index_ward"], errors="ignore")
    hf_clean.to_file(TMP_GPKG, layer="delta_health_facilities", driver="GPKG")
    pilot_summary.to_file(TMP_GPKG, layer="ward_facility_summary", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"\nAdded layers to {GPKG}: delta_lgas, delta_health_facilities, ward_facility_summary")


if __name__ == "__main__":
    main()
