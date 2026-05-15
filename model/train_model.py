"""Train Trellis 4-week-ahead forecast model with walk-forward time-series CV.

For each target (NO2, rainfall, temperature):
  - Walk forward: train on months [t0..t-1], predict month t, score
  - Compare against persistence (t1 = t) and climatology (t1 = mean of same month, prior years)
  - Final model: trained on all available data, ready for May 2026 prediction
"""
import json
import joblib
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent

DATA = (ROOT_DIR / "data")
MODEL = (ROOT_DIR / "model")

df = pd.read_csv(MODEL / "feature_table.csv")
df["ym"] = df["year"]*12 + df["month"]

TARGETS = ["no2_umol_m2", "rainfall_mm", "t2m_mean"]
FEATURES = [c for c in df.columns if c.endswith("_lag1") or c.endswith("_lag2") or c.endswith("_lag3")
            or c in ("month_sin","month_cos","flare_total_bcm_13yr","fac_total","fac_phc",
                       "pop_total","pop_under5","ndvi_annual")]
print(f"Features: {len(FEATURES)}")

results = {}

for target in TARGETS:
    target_col = f"{target}_t1"
    print(f"\n{'='*60}")
    print(f"TARGET: {target_col}")
    print(f"{'='*60}")

    valid = df.dropna(subset=[target_col])
    valid = valid.dropna(subset=FEATURES, how="all").reset_index(drop=True)
    # Fill remaining feature NAs with column means for stability
    for c in FEATURES:
        if valid[c].isna().any():
            valid[c] = valid[c].fillna(valid[c].mean())
    print(f"  rows with target + features: {len(valid)}")

    # Walk-forward CV: for each unique month from month 4 onwards, train on prior, predict it
    months_sorted = sorted(valid.ym.unique())
    fold_results = []
    persistence_results = []
    climatology_results = []

    for fold_month in months_sorted[4:]:
        train = valid[valid.ym < fold_month]
        test = valid[valid.ym == fold_month]
        if len(train) < 30 or len(test) == 0: continue

        model = xgb.XGBRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.85, colsample_bytree=0.85,
            random_state=42, verbosity=0,
        )
        model.fit(train[FEATURES], train[target_col])
        preds = model.predict(test[FEATURES])
        rmse = float(np.sqrt(mean_squared_error(test[target_col], preds)))
        mae = float(mean_absolute_error(test[target_col], preds))
        fold_results.append({"month": int(fold_month), "n": int(len(test)), "rmse": rmse, "mae": mae})

        # Persistence: predict t+1 = t (i.e. _lag1 of the t+1 reference is the value at t)
        # Actually the value at t IS in the lag1 of the t+1 row, but our table is indexed differently.
        # Use the corresponding non-shifted value: persistence means y_pred_t1 = y_t = lag1 of t1
        if f"{target}_lag1" in test.columns:
            pers = test[f"{target}_lag1"].values
            # Drop nan persistence rows from comparison
            mask = ~np.isnan(pers)
            if mask.any():
                p_rmse = float(np.sqrt(mean_squared_error(test.loc[mask, target_col], pers[mask])))
                persistence_results.append({"month": int(fold_month), "n": int(mask.sum()), "rmse": p_rmse})

        # Climatology: mean of same calendar month from prior data
        clim_month = test.month.iloc[0]
        clim_train = train[train.month == clim_month][target_col]
        if len(clim_train):
            clim_pred = clim_train.mean()
            c_rmse = float(np.sqrt(mean_squared_error(test[target_col], np.full(len(test), clim_pred))))
            climatology_results.append({"month": int(fold_month), "n": int(len(test)), "rmse": c_rmse})

    if not fold_results: continue
    cv_rmse = np.mean([r["rmse"] for r in fold_results])
    cv_mae = np.mean([r["mae"] for r in fold_results])
    pers_rmse = np.mean([r["rmse"] for r in persistence_results]) if persistence_results else None
    clim_rmse = np.mean([r["rmse"] for r in climatology_results]) if climatology_results else None
    print(f"  Walk-forward folds: {len(fold_results)}")
    print(f"  Model RMSE (avg over folds):       {cv_rmse:.3f}")
    print(f"  Model MAE  (avg over folds):       {cv_mae:.3f}")
    print(f"  Persistence RMSE (baseline):       {pers_rmse:.3f}" if pers_rmse else "  Persistence RMSE: n/a")
    print(f"  Climatology RMSE (baseline):       {clim_rmse:.3f}" if clim_rmse else "  Climatology RMSE: n/a")
    if pers_rmse:
        skill_pers = 1 - cv_rmse / pers_rmse
        print(f"  Skill score vs persistence:         {skill_pers:+.2%}")
    if clim_rmse:
        skill_clim = 1 - cv_rmse / clim_rmse
        print(f"  Skill score vs climatology:         {skill_clim:+.2%}")

    # Final model: train on all available labeled data
    final = xgb.XGBRegressor(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.85, colsample_bytree=0.85, random_state=42, verbosity=0,
    )
    final.fit(valid[FEATURES], valid[target_col])
    joblib.dump(final, MODEL / f"model_{target}.joblib")
    fi = pd.DataFrame({"feature": FEATURES, "importance": final.feature_importances_})
    fi = fi.sort_values("importance", ascending=False).reset_index(drop=True)
    print(f"  Top 5 features:")
    for _, r in fi.head(5).iterrows():
        print(f"    {r.feature:30s}  {r.importance:.3f}")
    fi.to_csv(MODEL / f"feature_importance_{target}.csv", index=False)

    results[target] = {
        "cv_rmse": cv_rmse, "cv_mae": cv_mae,
        "persistence_rmse": pers_rmse, "climatology_rmse": clim_rmse,
        "skill_vs_persistence": (1 - cv_rmse/pers_rmse) if pers_rmse else None,
        "skill_vs_climatology": (1 - cv_rmse/clim_rmse) if clim_rmse else None,
        "n_folds": len(fold_results), "n_train_total": int(len(valid)),
        "model_path": str(MODEL / f"model_{target}.joblib"),
    }

with open(MODEL / "skill_report.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nWrote skill report to {MODEL/'skill_report.json'}")