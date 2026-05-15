
# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent
"""Generate May 2026 forecast from trained models for all 51 pilot wards."""
import json
import joblib
from pathlib import Path
import pandas as pd
import numpy as np

DATA = (ROOT_DIR / "data")
MODEL = (ROOT_DIR / "model")
MVP = (ROOT_DIR / "mvp")

df = pd.read_csv(MODEL / "feature_table.csv")

# We need features at month T = April 2026 to predict May 2026 (T+1)
# That means: we need rows where year=2026 and month=4 — the "current" month.
# These rows already have lags 1, 2, 3 populated from March, Feb, Jan 2026.
current = df[(df.year == 2026) & (df.month == 4)].copy()
print(f"Pilot wards at April 2026 reference: {len(current)}")

FEATURES = [c for c in df.columns if c.endswith("_lag1") or c.endswith("_lag2") or c.endswith("_lag3")
            or c in ("month_sin","month_cos","flare_total_bcm_13yr","fac_total","fac_phc",
                       "pop_total","pop_under5","ndvi_annual")]

# Override month_sin/cos to reflect May (month 5) for the T+1 prediction
import math
current["month_sin"] = math.sin(2 * math.pi * 5 / 12)
current["month_cos"] = math.cos(2 * math.pi * 5 / 12)

# Fill missing features with column means
for c in FEATURES:
    if current[c].isna().any():
        current[c] = current[c].fillna(df[c].mean())

# Load models and predict
forecasts = current[["lganame","wardname","pop_under5","fac_phc","fac_total","flare_total_bcm_13yr"]].copy()
TARGETS = ["no2_umol_m2", "rainfall_mm", "t2m_mean"]
for target in TARGETS:
    model = joblib.load(MODEL / f"model_{target}.joblib")
    pred = model.predict(current[FEATURES])
    forecasts[f"{target}_forecast"] = pred.round(2)
    # Also retain the climatology (May value historical) for comparison
    same_mo = df[df.month == 5].groupby(["lganame","wardname"])[target].mean().reset_index()
    same_mo = same_mo.rename(columns={target: f"{target}_climatology"})
    forecasts = forecasts.merge(same_mo, on=["lganame","wardname"], how="left")

# Confidence tier based on forecast magnitude relative to climatology and model skill
def tier(row):
    no2 = row["no2_umol_m2_forecast"]
    clim = row["no2_umol_m2_climatology"]
    if pd.isna(no2): return "watch"
    if pd.isna(clim) or clim == 0:
        return "possible" if no2 > 25 else "watch"
    rel = (no2 - clim) / clim
    if no2 >= 25 and rel > 0.1: return "likely"
    if no2 >= 20 or rel > 0.15: return "possible"
    return "watch"

forecasts["tier"] = forecasts.apply(tier, axis=1)

# Save as drop-in replacement for the MVP forecast.json
mvp_payload = []
for _, r in forecasts.iterrows():
    mvp_payload.append({
        "lganame": r["lganame"],
        "wardname": r["wardname"],
        "forecast_year": 2026, "forecast_month": 5,
        "no2_forecast_umol_m2": float(r["no2_umol_m2_forecast"]) if not pd.isna(r["no2_umol_m2_forecast"]) else None,
        "rainfall_forecast_mm": float(r["rainfall_mm_forecast"]) if not pd.isna(r["rainfall_mm_forecast"]) else None,
        "t2m_forecast_c": float(r["t2m_mean_forecast"]) if not pd.isna(r["t2m_mean_forecast"]) else None,
        "no2_climatology": float(r["no2_umol_m2_climatology"]) if not pd.isna(r["no2_umol_m2_climatology"]) else None,
        "tier": r["tier"],
        "model": "xgboost_v1",
        "n_obs": 12,  # months of training data per ward (approximate)
    })

with open(MVP / "forecast_may_2026.json", "w") as f:
    json.dump(mvp_payload, f, indent=2)

forecasts.to_csv(MODEL / "forecast_may_2026.csv", index=False)
print(f"Wrote {MVP/'forecast_may_2026.json'}: {len(mvp_payload)} wards")
print(f"\nForecast distribution:")
print(forecasts["tier"].value_counts().to_string())
print(f"\nMay 2026 forecast NO2 by LGA (μmol/m²):")
print(forecasts.groupby("lganame")["no2_umol_m2_forecast"].describe()[["mean","min","max"]].round(2).to_string())
print(f"\nTop 10 wards by forecast NO2:")
print(forecasts.nlargest(10, "no2_umol_m2_forecast")[
    ["lganame","wardname","no2_umol_m2_forecast","no2_umol_m2_climatology","rainfall_mm_forecast","tier","pop_under5"]
].to_string(index=False))