"""Allocate the 25-sensor network across the five pilot LGAs.

Constraints:
  - 10 PHC sensors, 10 school sensors, 5 community sensors (per trellis.md)
  - Every LGA gets at least one node in each channel
  - PHC nodes pair to wards with at least one PHC (so the sensor has a host)
  - School nodes can go anywhere with a primary school (we accept that as given;
    placement is by ward, host school identification is a Phase-1 deliverable)
  - Community nodes go to wards with zero facilities or to mangrove/coastal wards

Output: data/siting/sensor_allocation.csv with one row per node.
"""

import shutil

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path

import geopandas as gpd
import pandas as pd

ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DATA = ROOT_DIR / "data"
SITING = DATA / "siting"
GPKG = DATA / "trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"

ALLOCATION = [
    # (lganame, wardname, channel, rationale)
    # PHC nodes (10)
    (
        "Warri South",
        "Ekurede",
        "PHC",
        "Rank 1 overall; 12k under-5; second-highest NO2; 11 PHCs to host the node",
    ),
    ("Warri South", "Ubeji", "PHC", "Rank 2; 10k under-5; refinery-vicinity ward; 6 PHCs"),
    ("Warri South", "Okere", "PHC", "Rank 3; 9k under-5; 10 PHCs; central Warri urban core"),
    (
        "Warri South-West",
        "Ugborodo",
        "PHC",
        "Flare-belt centre; Escravos terminal vicinity; underserved PHCs",
    ),
    ("Warri South-West", "Ogbe-Ijoh", "PHC", "Flare-belt north; 4 PHCs to host; second WSW node"),
    ("Bomadi", "Bomadi", "PHC", "LGA centre; 5,800 under-5; 3 PHCs; primary Bomadi catchment"),
    ("Bomadi", "Kpakiama", "PHC", "Riverine secondary; 2,800 under-5; second Bomadi node"),
    ("Patani", "Patani 5", "PHC", "Patani score-leader with at least one PHC; 2,200 under-5"),
    ("Burutu", "Ogulagha", "PHC", "Forcados estuary; 5k under-5; 5 PHCs; flare-and-population overlap"),
    ("Burutu", "Kiagbodo", "PHC", "Burutu second node; riverine coverage; 2,500 under-5"),
    # School nodes (10)
    ("Warri South", "Pessu", "school", "Highest single-ward NO2 in the pilot (30 umol/m^2)"),
    (
        "Warri South",
        "Igbudu",
        "school",
        "Largest under-5 pop; 14 PHCs to anchor a multi-stakeholder partnership",
    ),
    ("Warri South-West", "Okerenkoko", "school", "Flare-belt school; high flare exposure with limited PHCs"),
    (
        "Warri South-West",
        "Ajudaibo",
        "school",
        "Coastal mangrove sentinel; low pop but in the flare-corridor",
    ),
    (
        "Bomadi",
        "Akugbene 1",
        "school",
        "Bomadi equity ward; 0 PHCs; school is the only health-adjacent observation point",
    ),
    ("Bomadi", "Esanma", "school", "Riverine Bomadi school; pairs with Kpakiama PHC catchment"),
    (
        "Patani",
        "Patani 2",
        "school",
        "Zero facilities, zero PHCs; school is the only candidate node site in this ward",
    ),
    ("Patani", "Agoloma", "school", "Patani top NO2 (22 umol/m^2); pairs with Patani 5 PHC catchment"),
    ("Burutu", "Tuomo", "school", "Riverine bridge between Bomadi and Burutu LGA boundaries"),
    (
        "Burutu",
        "Bolou-Ndoro",
        "school",
        "Inland Burutu coverage; complements Ogulagha and Kiagbodo PHC nodes",
    ),
    # Community nodes (5)
    (
        "Warri South",
        "Avenue",
        "community",
        "Mid-density urban Warri; complements Ekurede/Ubeji refinery cluster",
    ),
    ("Warri South-West", "Akpakpa", "community", "Zero facilities; mangrove community; equity-driven"),
    ("Bomadi", "Akugbene 2", "community", "Zero facilities; zero captured population in WorldPop (mangrove)"),
    (
        "Patani",
        "Buluangiama",
        "community",
        "Patani LGA broad-coverage community node; one of the higher-NO2 Patani wards (29 umol/m^2 in April)",
    ),
    ("Burutu", "Ojobo", "community", "Forcados estuary community; rural Burutu"),
]


def main():
    df = pd.DataFrame(ALLOCATION, columns=["lganame", "wardname", "channel", "rationale"])
    df["node_id"] = ["TR-" + str(i + 1).zfill(2) for i in range(len(df))]

    scores = pd.read_csv(SITING / "ward_siting_scores.csv")
    df = df.merge(
        scores[
            [
                "lganame",
                "wardname",
                "score",
                "rank",
                "pop_under5",
                "no2_umol_m2_mean",
                "fac_phc",
                "flare_total_bcm_13yr",
            ]
        ],
        on=["lganame", "wardname"],
        how="left",
    )
    df = df[
        [
            "node_id",
            "channel",
            "lganame",
            "wardname",
            "rank",
            "score",
            "pop_under5",
            "no2_umol_m2_mean",
            "fac_phc",
            "flare_total_bcm_13yr",
            "rationale",
        ]
    ]
    df.to_csv(SITING / "sensor_allocation.csv", index=False)

    print("Sensor allocation summary:")
    print(f"  total nodes: {len(df)}")
    print(f"  by channel: {df.channel.value_counts().to_dict()}")
    print("  by LGA:")
    print(df.groupby(["lganame", "channel"]).size().unstack(fill_value=0).to_string())
    print()
    for ch in ("PHC", "school", "community"):
        print(f"\n=== {ch} ({len(df[df.channel == ch])}) ===")
        print(
            df[df.channel == ch][
                ["node_id", "lganame", "wardname", "rank", "pop_under5", "no2_umol_m2_mean", "fac_phc"]
            ].to_string(index=False)
        )

    # GeoPackage layer with polygons
    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    nodes_geo = pilot.merge(df, on=["lganame", "wardname"], how="inner")
    # Use centroid of ward as candidate site location
    centroids_proj = nodes_geo.to_crs("EPSG:32632").geometry.centroid.to_crs("EPSG:4326")
    nodes_geo["site_lon"] = centroids_proj.x
    nodes_geo["site_lat"] = centroids_proj.y
    nodes_geo.to_file(TMP_GPKG, layer="sensor_sites", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"\nWrote {SITING / 'sensor_allocation.csv'}")
    print(f"Added layer 'sensor_sites' to {GPKG}")


if __name__ == "__main__":
    main()
