"""Compute a defensible composite sensor-siting priority score per pilot ward.

Scoring rationale: a sensor's value at a ward is proportional to (a) how many
children it would protect, (b) how strong the pollutant signal is at that
location, (c) whether the ward is otherwise underserved by facilities, and
(d) whether it sits in or next to the persistent-flare exposure corridor.

We compute four normalized component scores in [0,1] and a weighted sum.
Weights are made explicit so reviewers can interrogate them.

components:
  exposure_child  = pop_under5 normalized           # who we protect
  exposure_no2    = no2_mean (12-month) normalized  # exposure signal
  exposure_flare  = flare_total_bcm (or proximity)  # industrial source
  coverage_gap    = inverse of phc_per_1k_u5        # service deficit (higher = worse coverage)

weights:
  exposure_child : 0.35   # children-first
  exposure_no2   : 0.25   # measurable exposure
  exposure_flare : 0.15   # industrial exposure (sparse but real)
  coverage_gap   : 0.25   # equity / underserved
"""

import shutil

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path

import geopandas as gpd
import pandas as pd

ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DATA = ROOT_DIR / "data"
GPKG = DATA / "trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"
OUT = DATA / "siting"
OUT.mkdir(exist_ok=True)

WEIGHTS = dict(exposure_child=0.35, exposure_no2=0.25, exposure_flare=0.15, coverage_gap=0.25)


def main():
    df = pd.read_csv(DATA / "predictors/trellis_ward_month_predictors.csv")
    # Reduce to per-ward (collapse the time dimension by using mean / max where appropriate)
    static = (
        df.groupby(["lganame", "wardname"])
        .agg(
            no2_umol_m2_mean=("no2_umol_m2", "mean"),
            no2_valid_pixels_total=("no2_valid_pixels", "sum"),
            rainfall_mm_mean=("rainfall_mm", "mean"),
            t2m_mean=("t2m_mean", "mean"),
            flare_n_sites=("flare_n_sites", "first"),
            flare_total_bcm_13yr=("flare_total_bcm_13yr", "first"),
            fac_total=("fac_total", "first"),
            fac_phc=("fac_phc", "first"),
            pop_total=("pop_total", "first"),
            pop_under5=("pop_under5", "first"),
            phc_per_1k_u5=("phc_per_1k_u5", "first"),
        )
        .reset_index()
    )

    # Replace NaN no2 with LGA mean (we'd rather propose sensors in low-coverage wards, not penalize them)
    static["no2_umol_m2_for_score"] = static["no2_umol_m2_mean"]
    lga_mean = static.groupby("lganame")["no2_umol_m2_mean"].transform("mean")
    static["no2_umol_m2_for_score"] = static["no2_umol_m2_for_score"].fillna(lga_mean)

    # Normalize each component to [0,1]
    def norm01(s):
        s = pd.Series(s).astype(float)
        if s.max() == s.min():
            return s * 0
        return (s - s.min()) / (s.max() - s.min())

    static["score_child"] = norm01(static["pop_under5"])
    static["score_no2"] = norm01(static["no2_umol_m2_for_score"])
    static["score_flare"] = norm01(static["flare_total_bcm_13yr"])

    # Coverage gap: invert phc_per_1k_u5; wards with 0 PHCs per 1k get max gap.
    # Use a "deficit" definition: wards with no PHC get score 1; wards with the most PHCs get 0.
    # Cap at 95th pct to avoid one extreme value flattening the rest.
    cap = static["phc_per_1k_u5"].quantile(0.95)
    capped = static["phc_per_1k_u5"].clip(upper=cap)
    static["score_coverage_gap"] = 1 - norm01(capped)

    # Composite score
    static["score"] = (
        WEIGHTS["exposure_child"] * static["score_child"]
        + WEIGHTS["exposure_no2"] * static["score_no2"]
        + WEIGHTS["exposure_flare"] * static["score_flare"]
        + WEIGHTS["coverage_gap"] * static["score_coverage_gap"]
    ).round(3)

    static = static.sort_values("score", ascending=False).reset_index(drop=True)
    static["rank"] = static.index + 1

    print("Top 15 wards by composite siting score:")
    print(
        static.head(15)[
            [
                "rank",
                "lganame",
                "wardname",
                "score",
                "pop_under5",
                "no2_umol_m2_mean",
                "flare_total_bcm_13yr",
                "fac_phc",
                "phc_per_1k_u5",
            ]
        ].to_string(index=False)
    )

    print("\nBottom 5 (least priority):")
    print(
        static.tail(5)[
            ["rank", "lganame", "wardname", "score", "pop_under5", "no2_umol_m2_mean", "fac_phc"]
        ].to_string(index=False)
    )

    # Per-LGA top wards
    print("\nTop 3 wards per pilot LGA:")
    for lga, group in static.groupby("lganame", sort=False):
        top3 = group.nlargest(3, "score")[["wardname", "score", "pop_under5", "no2_umol_m2_mean", "fac_phc"]]
        print(f"\n[{lga}]")
        print(top3.to_string(index=False))

    static.to_csv(OUT / "ward_siting_scores.csv", index=False)
    # Add to GeoPackage
    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    pilot_scored = pilot.merge(
        static.drop(columns=["no2_umol_m2_for_score"], errors="ignore"),
        on=["lganame", "wardname"],
        how="left",
    )
    pilot_scored.to_file(TMP_GPKG, layer="ward_siting_scores", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"\nWrote {OUT / 'ward_siting_scores.csv'}")
    print(f"Added layer 'ward_siting_scores' to {GPKG}")


if __name__ == "__main__":
    main()
