"""Build a rolling forecast horizon for Trellis from now through end of 2026.

Approach C — hybrid (operationally standard):
  - May 2026: kept from the trained XGBoost model (1-month-ahead, validated)
  - Jun-Dec 2026: climatology — historical same-calendar-month means
    across 2019-2025 (7 years of overlap data with all three predictors).
    Climatology beats the model recursively at horizons past 1 month for
    seasonal environmental variables, and is what NOAA / ECMWF / WHO EWARS
    do for far-out outlooks.

Each output JSON is a 51-ward forecast per month, with the same schema as
mvp/forecast_may_2026.json so push_to_dhis2.py can consume it unchanged
(plus a small extension to accept multiple period files).

The malaria-risk tier (model/malaria_risk.py) is applied to each month.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PREDICTORS = ROOT / "data/predictors/trellis_ward_month_predictors.csv"
MVP_DIR = ROOT / "mvp"
DHIS2_LOCAL_DIR = ROOT / "dhis2/local"

sys.path.insert(0, str(ROOT / "model"))
from malaria_risk import classify_malaria_risk  # noqa: E402


def build_climatology() -> pd.DataFrame:
    """Per-ward × calendar-month climatology of the three forecast targets.

    Use 2019-2025 inclusive (7 years) — Sentinel-5P came online late 2018
    so 2019 onwards is the cleanest overlap across NO2 / rainfall / temp.
    """
    df = pd.read_csv(PREDICTORS)
    df = df[(df["year"] >= 2019) & (df["year"] <= 2025)].copy()
    g = (
        df.groupby(["lganame", "wardname", "month"])
        .agg(
            no2_climo=("no2_umol_m2", "mean"),
            rain_climo=("rainfall_mm", "mean"),
            temp_climo=("t2m_mean", "mean"),
        )
        .reset_index()
    )
    return g


def build_month_forecast(climo: pd.DataFrame, year: int, month: int) -> list[dict]:
    """Return a forecast list for a given calendar month, climatology-based."""
    sub = climo[climo["month"] == month].copy()
    out = []
    for _, r in sub.iterrows():
        no2 = float(r["no2_climo"])
        rain = float(r["rain_climo"])
        temp = float(r["temp_climo"])
        # Generic alert tier reuses the existing simple rule:
        #   likely if NO2 above 75th pct of pilot wards
        #   possible if NO2 above 50th pct
        #   else watch
        # We compute the threshold below from this month's pool.
        out.append(
            {
                "lganame": r["lganame"],
                "wardname": r["wardname"],
                "forecast_year": year,
                "forecast_month": month,
                "no2_forecast_umol_m2": round(no2, 3),
                "rainfall_forecast_mm": round(rain, 3),
                "t2m_forecast_c": round(temp, 3),
                "no2_climatology": round(no2, 3),  # by definition
                "model": "climatology_v1",
                "method_note": "Climatology-based seasonal expectation (mean of 2019-2025). "
                "Use for horizons >1 month, where model skill degrades.",
                "n_obs": 7,  # 7 years of climatology
            }
        )
    if not out:
        return out
    no2_vals = sorted([w["no2_forecast_umol_m2"] for w in out])
    p75 = no2_vals[int(len(no2_vals) * 0.75)]
    p50 = no2_vals[int(len(no2_vals) * 0.50)]
    for w in out:
        n = w["no2_forecast_umol_m2"]
        w["tier"] = "likely" if n >= p75 else ("possible" if n >= p50 else "watch")
        # Malaria tier
        w["malaria_risk_tier"] = classify_malaria_risk(w["rainfall_forecast_mm"], w["t2m_forecast_c"])
    return out


def main():
    climo = build_climatology()
    print(f"Climatology built: {len(climo)} ward × month combinations from 2019-2025")

    # Months to generate climatology forecasts for. May 2026 is already done by the model;
    # we keep that file untouched. June through December 2026 from climatology.
    targets = [(2026, m) for m in (6, 7, 8, 9, 10, 11, 12)]

    summary = {}
    for year, month in targets:
        rows = build_month_forecast(climo, year, month)
        summary[f"{year}-{month:02d}"] = {
            "n_wards": len(rows),
            "tier_likely": sum(1 for r in rows if r["tier"] == "likely"),
            "tier_possible": sum(1 for r in rows if r["tier"] == "possible"),
            "tier_watch": sum(1 for r in rows if r["tier"] == "watch"),
            "malaria_likely": sum(1 for r in rows if r["malaria_risk_tier"] == "likely"),
            "malaria_possible": sum(1 for r in rows if r["malaria_risk_tier"] == "possible"),
            "malaria_watch": sum(1 for r in rows if r["malaria_risk_tier"] == "watch"),
        }
        # Write to mvp/ and dhis2/local/ — push_to_dhis2.py reads from the latter
        for d in (MVP_DIR, DHIS2_LOCAL_DIR):
            p = d / f"forecast_{year}_{month:02d}.json"
            p.write_text(json.dumps(rows, indent=2))
            print(f"  wrote {p}")

    print("\nSummary:")
    for ym, s in summary.items():
        print(f"  {ym}: {s}")


if __name__ == "__main__":
    main()
