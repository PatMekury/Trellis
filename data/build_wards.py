"""Build trellis_delta_wards.gpkg from GRID3 NGA Operational Wards v2.0.

Pulls Delta State wards directly from the GRID3 v2.0 ArcGIS Feature Service,
renames fields to the Trellis canonical schema, and writes a two-layer
GeoPackage: statewide (delta_wards) and pilot LGAs (pilot_wards).

Source: GRID3 NGA - Operational Wards v2.0 (ArcGIS item 9ab61cff803a497986bf2716898c6902)
"""
from pathlib import Path
import shutil
import subprocess
import geopandas as gpd

HERE = Path(__file__).parent
TMP_GEOJSON = HERE / "delta_wards_v2.geojson"
TMP_GPKG = Path("/tmp/trellis_delta_wards.gpkg")
FINAL_GPKG = HERE / "trellis_delta_wards.gpkg"

SERVICE = (
    "https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/"
    "main_GRID3_NGA_operational_wards_v2_0/FeatureServer/0/query"
)
PILOT_LGAS = {"warri south", "warri south west", "burutu", "bomadi", "patani"}


def norm(s: str) -> str:
    return str(s).lower().replace("-", " ").strip()


def fetch_delta() -> Path:
    if TMP_GEOJSON.exists():
        return TMP_GEOJSON
    cmd = [
        "curl", "-sL", "--get", SERVICE,
        "--data-urlencode", "where=state='Delta'",
        "--data-urlencode", "outFields=*",
        "--data-urlencode", "outSR=4326",
        "--data-urlencode", "f=geojson",
        "-o", str(TMP_GEOJSON),
    ]
    subprocess.run(cmd, check=True)
    return TMP_GEOJSON


def build():
    src = fetch_delta()
    delta = gpd.read_file(src)

    # Rename v2.0 fields to Trellis canonical schema
    delta = delta.rename(columns={
        "state": "statename",
        "lga": "lganame",
        "ward": "wardname",
    })
    for col in ("OBJECTID", "Shape__Area", "Shape__Length"):
        if col in delta.columns:
            delta = delta.drop(columns=col)

    pilot = delta[delta["lganame"].apply(lambda x: norm(x) in PILOT_LGAS)].copy()

    print(f"delta: {len(delta)}  null geom: {delta.geometry.isna().sum()}  "
          f"all valid: {delta.is_valid.all()}")
    print(f"pilot: {len(pilot)}  null geom: {pilot.geometry.isna().sum()}  "
          f"all valid: {pilot.is_valid.all()}")

    # SQLite struggles with mounted filesystems - write to /tmp, then copy
    if TMP_GPKG.exists():
        TMP_GPKG.unlink()
    delta.to_file(TMP_GPKG, layer="delta_wards", driver="GPKG")
    pilot.to_file(TMP_GPKG, layer="pilot_wards", driver="GPKG")
    shutil.copy2(TMP_GPKG, FINAL_GPKG)
    print(f"Wrote {FINAL_GPKG} ({FINAL_GPKG.stat().st_size / 1024:.1f} KB)")

    print("\nPilot LGA ward counts:")
    for lga, n in pilot["lganame"].value_counts().items():
        print(f"  {lga}: {n}")
    b = pilot.total_bounds
    print(f"\nPilot bbox (W S E N): {b[0]:.4f} {b[1]:.4f} {b[2]:.4f} {b[3]:.4f}")


if __name__ == "__main__":
    build()
