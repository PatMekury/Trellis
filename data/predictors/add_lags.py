"""Add lagged rainfall and temperature columns to the predictor table.

Lags: 1 month (~4 weeks), 2 months (~8 weeks), 3 months (~12 weeks).
For wards on the leading edge of the time window, lags will be NaN.

The window is May 2025 - April 2026, so:
  - 1-month lag has 11 valid month rows per ward
  - 2-month lag has 10 valid
  - 3-month lag has  9 valid

For operational use the upstream pull would extend further back to avoid this edge.
"""
from pathlib import Path
import pandas as pd

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DATA = (ROOT_DIR / "data/predictors")
csv = DATA / "trellis_ward_month_predictors.csv"

df = pd.read_csv(csv)
df = df.sort_values(["lganame","wardname","year","month"]).reset_index(drop=True)

# Build a sortable t column
df["t"] = df["year"] * 12 + df["month"]

# For each lag, group by ward and shift
def add_lag(col, lag, suffix):
    df[f"{col}_lag{suffix}"] = df.groupby(["lganame","wardname"])[col].shift(lag)

for col in ["rainfall_mm", "t2m_mean"]:
    for lag, suffix in [(1, "1m"), (2, "2m"), (3, "3m")]:
        add_lag(col, lag, suffix)

# Drop helper
df = df.drop(columns=["t"])

# Reorder so lagged columns sit next to their base
def insert_after(cols, base, lagged):
    out = []
    for c in cols:
        out.append(c)
        if c == base:
            out.extend(lagged)
    return out

cols = list(df.columns)
# Remove lagged from end to reinsert
lag_rain = [c for c in cols if c.startswith("rainfall_mm_lag")]
lag_t = [c for c in cols if c.startswith("t2m_mean_lag")]
cols = [c for c in cols if c not in lag_rain + lag_t]
cols = insert_after(cols, "rainfall_valid_pixels", lag_rain)
cols = insert_after(cols, "ts_mean", lag_t)
df = df[cols]

df.to_csv(csv, index=False)
print(f"Updated {csv}: {len(df)} rows x {len(df.columns)} columns")

# Coverage report
for c in lag_rain + lag_t:
    print(f"  {c:30s}  non-null: {df[c].notna().sum()} ({df[c].notna().mean()*100:.1f}%)")

# Sanity: print one ward's series
sub = df[(df.lganame=="Warri South") & (df.wardname=="Pessu")][
    ["ym","rainfall_mm","rainfall_mm_lag1m","rainfall_mm_lag2m","t2m_mean","t2m_mean_lag1m"]
].head(13)
print("\nSanity check — Warri South / Pessu:")
print(sub.to_string(index=False))