"""Generate a high-signal December 2025 forecast for dashboard demonstration.

The Niger Delta's December is the Harmattan peak — northeasterly trade winds
carry biomass-burning aerosols south, so monthly NO2 surges. Producing a
December forecast from November features lets the dashboard demonstrate the
trained model in both wet-season (May 2026) and dry-season (December 2025)
regimes, which is otherwise lost in a single-month demo.

Run from the repository root:
    cd model
    python3 forecast_dec2025.py

This writes mvp/forecast_dec_2025.json which the dashboards can switch to.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "model"
MVP = ROOT / "mvp"

df = pd.read_csv(MODEL / "feature_table_multiyear.csv")
current = df[(df.year == 2025) & (df.month == 11)].copy()
print(f"Reference rows (Nov 2025): {len(current)}")

FEATURES = [
    c
    for c in df.columns
    if c.endswith("_lag1")
    or c.endswith("_lag2")
    or c.endswith("_lag3")
    or c
    in (
        "month_sin",
        "month_cos",
        "flare_total_bcm_13yr",
        "fac_total",
        "fac_phc",
        "pop_total",
        "pop_under5",
        "ndvi_annual",
    )
]

# Override seasonal encoding to point at December
current["month_sin"] = math.sin(2 * math.pi * 12 / 12)
current["month_cos"] = math.cos(2 * math.pi * 12 / 12)
for c in FEATURES:
    if current[c].isna().any():
        current[c] = current[c].fillna(df[c].mean())

forecasts = current[
    ["lganame", "wardname", "pop_under5", "fac_phc", "fac_total", "flare_total_bcm_13yr"]
].copy()

TARGETS = ["no2_umol_m2", "rainfall_mm", "t2m_mean"]
for target in TARGETS:
    model = joblib.load(MODEL / f"model_{target}.joblib")
    pred = model.predict(current[FEATURES])
    forecasts[f"{target}_forecast"] = pred.round(2)
    same_mo = df[df.month == 12].groupby(["lganame", "wardname"])[target].mean().reset_index()
    same_mo = same_mo.rename(columns={target: f"{target}_climatology"})
    forecasts = forecasts.merge(same_mo, on=["lganame", "wardname"], how="left")


def tier(row):
    no2 = row["no2_umol_m2_forecast"]
    clim = row["no2_umol_m2_climatology"]
    if pd.isna(no2):
        return "watch"
    if pd.isna(clim) or clim == 0:
        return "possible" if no2 > 25 else "watch"
    rel = (no2 - clim) / clim
    if no2 >= 25 and rel > 0.1:
        return "likely"
    if no2 >= 20 or rel > 0.15:
        return "possible"
    return "watch"


forecasts["tier"] = forecasts.apply(tier, axis=1)

mvp_payload = []
for _, r in forecasts.iterrows():
    mvp_payload.append(
        {
            "lganame": r["lganame"],
            "wardname": r["wardname"],
            "forecast_year": 2025,
            "forecast_month": 12,
            "no2_forecast_umol_m2": (
                float(r["no2_umol_m2_forecast"]) if not pd.isna(r["no2_umol_m2_forecast"]) else None
            ),
            "rainfall_forecast_mm": (
                float(r["rainfall_mm_forecast"]) if not pd.isna(r["rainfall_mm_forecast"]) else None
            ),
            "t2m_forecast_c": (
                float(r["t2m_mean_forecast"]) if not pd.isna(r["t2m_mean_forecast"]) else None
            ),
            "no2_climatology": (
                float(r["no2_umol_m2_climatology"]) if not pd.isna(r["no2_umol_m2_climatology"]) else None
            ),
            "tier": r["tier"],
            "model": "xgboost_v2_multiyear",
            "n_obs": 91,
        }
    )

(MVP / "forecast_dec_2025.json").write_text(json.dumps(mvp_payload, indent=2))
print(f"Wrote {MVP / 'forecast_dec_2025.json'}: {len(mvp_payload)} wards")
print("\nTier distribution:")
print(forecasts.tier.value_counts().to_string())
print("\nLGA mean forecast NO2 (μmol/m²):")
print(forecasts.groupby("lganame")["no2_umol_m2_forecast"].mean().round(2).to_string())
