"""Engineer features for the Trellis 4-week-ahead forecast model.

Target variables: NO2, rainfall, temperature at month T+1.
Features at month T:
  - Self lags: target value at T, T-1, T-2, T-3
  - Cross lags: other EO predictors at T, T-1, T-2
  - Static: flares, facilities, population, ward/LGA categorical
  - Seasonal: month-of-year as cyclic encoding
"""
from pathlib import Path
import pandas as pd
import numpy as np

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent

DATA = (ROOT_DIR / "data")
MODEL = (ROOT_DIR / "model")
MODEL.mkdir(exist_ok=True)

df = pd.read_csv(DATA / "predictors/trellis_ward_month_predictors.csv")
df["t"] = df["year"] * 12 + df["month"]
df = df.sort_values(["lganame","wardname","t"]).reset_index(drop=True)

# Time-varying targets
TARGETS = ["no2_umol_m2", "rainfall_mm", "t2m_mean"]

# Build lagged features per ward
out = df.copy()
for col in TARGETS + ["ndvi"]:
    if col not in out.columns: continue
    for lag in (1, 2, 3):
        out[f"{col}_lag{lag}"] = out.groupby(["lganame","wardname"])[col].shift(lag)

# Cyclic month encoding
out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12)
out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12)

# Target: T+1 value
for col in TARGETS:
    out[f"{col}_t1"] = out.groupby(["lganame","wardname"])[col].shift(-1)

# Drop rows with no target value
out_target = out.dropna(subset=[f"{c}_t1" for c in TARGETS], how="all")
print(f"Total rows: {len(out)}")
print(f"Rows with at least one target: {len(out_target)}")
for c in TARGETS:
    print(f"  {c}_t1 non-null: {out[f'{c}_t1'].notna().sum()}")

# Save the engineered table
out.to_csv(MODEL / "feature_table.csv", index=False)
print(f"Wrote {MODEL/'feature_table.csv'}: {len(out)} rows x {len(out.columns)} cols")

# Print column inventory
print("\nFeature columns (excluding targets, identifiers):")
keep_cols = [c for c in out.columns if c.endswith("_lag1") or c.endswith("_lag2") or c.endswith("_lag3")
             or c in ("month_sin","month_cos","flare_total_bcm_13yr","fac_total","fac_phc",
                       "pop_total","pop_under5","ndvi_annual")]
print(f"  count: {len(keep_cols)}")
for c in keep_cols: print(f"    {c}")