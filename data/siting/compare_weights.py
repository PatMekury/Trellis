"""Compare 25-node allocation under four weighting schemes.

Weighting schemes (each row sums to 1):
  baseline:  child=0.35  no2=0.25  flare=0.15  coverage_gap=0.25
  child:     child=1.00  no2=0.00  flare=0.00  coverage_gap=0.00
  exposure:  child=0.00  no2=0.50  flare=0.50  coverage_gap=0.00   # combined pollution exposure
  equity:    child=0.00  no2=0.00  flare=0.00  coverage_gap=1.00

For each scheme we recompute the score, then re-allocate the 25 nodes using the
same channel/LGA-coverage rules as the baseline allocation:
  - each LGA gets >= 1 PHC, >= 1 school, >= 1 community
  - PHC nodes go to top-scoring wards in each LGA that have at least one PHC
  - school nodes prefer wards not already used as PHC nodes
  - community nodes prefer zero-facility wards within LGA, then top-score
"""

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path

import pandas as pd

ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DATA = ROOT_DIR / "data"
SITING = DATA / "siting"

WEIGHTINGS = {
    "baseline": dict(child=0.35, no2=0.25, flare=0.15, coverage_gap=0.25),
    "child": dict(child=1.00, no2=0.00, flare=0.00, coverage_gap=0.00),
    "exposure": dict(child=0.00, no2=0.50, flare=0.50, coverage_gap=0.00),
    "equity": dict(child=0.00, no2=0.00, flare=0.00, coverage_gap=1.00),
}

# LGA quotas: PHC, school, community (must total 10/10/5)
LGA_QUOTAS = {
    "Warri South": dict(phc=3, school=2, community=1),
    "Warri South-West": dict(phc=2, school=2, community=1),
    "Bomadi": dict(phc=2, school=2, community=1),
    "Burutu": dict(phc=2, school=2, community=1),
    "Patani": dict(phc=1, school=2, community=1),
}


def norm01(s):
    s = pd.Series(s).astype(float)
    if s.max() == s.min():
        return s * 0
    return (s - s.min()) / (s.max() - s.min())


def score_under(w, df):
    out = df.copy()
    no2 = out["no2_umol_m2_for_score"].fillna(out["no2_umol_m2_for_score"].mean())
    out["score"] = (
        w["child"] * norm01(out["pop_under5"])
        + w["no2"] * norm01(no2)
        + w["flare"] * norm01(out["flare_total_bcm_13yr"])
        + w["coverage_gap"]
        * (1 - norm01(out["phc_per_1k_u5"].clip(upper=out["phc_per_1k_u5"].quantile(0.95))))
    ).round(3)
    return out


def allocate(scored):
    selected = []
    used = set()
    for lga, quota in LGA_QUOTAS.items():
        sub = scored[scored.lganame == lga].sort_values("score", ascending=False)
        # PHC: top-N with at least one PHC
        phc_candidates = sub[sub.fac_phc >= 1]
        chosen_phc = []
        for _, r in phc_candidates.iterrows():
            key = (r.lganame, r.wardname)
            if key in used:
                continue
            chosen_phc.append(r)
            used.add(key)
            if len(chosen_phc) >= quota["phc"]:
                break
        # School: next top-N not already used
        chosen_school = []
        for _, r in sub.iterrows():
            key = (r.lganame, r.wardname)
            if key in used:
                continue
            chosen_school.append(r)
            used.add(key)
            if len(chosen_school) >= quota["school"]:
                break
        # Community: prefer zero-facility wards in LGA, fall back to remaining top score
        zero_fac = sub[sub.fac_total == 0]
        chosen_community = []
        for _, r in zero_fac.iterrows():
            key = (r.lganame, r.wardname)
            if key in used:
                continue
            chosen_community.append(r)
            used.add(key)
            if len(chosen_community) >= quota["community"]:
                break
        for _, r in sub.iterrows():
            if len(chosen_community) >= quota["community"]:
                break
            key = (r.lganame, r.wardname)
            if key in used:
                continue
            chosen_community.append(r)
            used.add(key)
        for r in chosen_phc:
            selected.append({"lganame": r.lganame, "wardname": r.wardname, "channel": "PHC"})
        for r in chosen_school:
            selected.append({"lganame": r.lganame, "wardname": r.wardname, "channel": "school"})
        for r in chosen_community:
            selected.append({"lganame": r.lganame, "wardname": r.wardname, "channel": "community"})
    return pd.DataFrame(selected)


def main():
    df = pd.read_csv(SITING / "ward_siting_scores.csv")
    df["no2_umol_m2_for_score"] = df["no2_umol_m2_mean"]
    lga_mean = df.groupby("lganame")["no2_umol_m2_mean"].transform("mean")
    df["no2_umol_m2_for_score"] = df["no2_umol_m2_for_score"].fillna(lga_mean)
    df["fac_total"] = df.get("fac_total", 0)  # may not exist
    if "fac_total" not in df.columns:
        # Pull from predictor table
        pred = pd.read_csv(DATA / "predictors/trellis_ward_month_predictors.csv")
        fac = pred.groupby(["lganame", "wardname"])["fac_total"].first().reset_index()
        df = df.merge(fac, on=["lganame", "wardname"], how="left")

    allocations = {}
    for name, w in WEIGHTINGS.items():
        scored = score_under(w, df)
        alloc = allocate(scored)
        allocations[name] = alloc
        print(
            f"\n=== {name.upper()} weighting (child={w['child']}, no2={w['no2']}, flare={w['flare']}, gap={w['coverage_gap']}) ==="
        )
        print(f"  total nodes: {len(alloc)}")

    # Compare allocations: which wards appear in baseline vs not?
    base_wards = set(zip(allocations["baseline"]["lganame"], allocations["baseline"]["wardname"]))

    print(f"\n{'=' * 80}")
    print("Per-weighting comparison (vs baseline):")
    for name in ("child", "exposure", "equity"):
        wards = set(zip(allocations[name]["lganame"], allocations[name]["wardname"]))
        common = base_wards & wards
        only_alt = wards - base_wards
        only_base = base_wards - wards
        print(f"\n--- {name} vs baseline ---")
        print(f"  shared with baseline: {len(common)} of 25")
        print(f"  in {name} but not baseline ({len(only_alt)}):")
        for lga, w in sorted(only_alt):
            print(f"    {lga} / {w}")
        print(f"  in baseline but not {name} ({len(only_base)}):")
        for lga, w in sorted(only_base):
            print(f"    {lga} / {w}")

    # Stable core: wards that appear in ALL FOUR allocations
    all_sets = [set(zip(a["lganame"], a["wardname"])) for a in allocations.values()]
    stable_core = set.intersection(*all_sets)
    print(f"\n{'=' * 80}")
    print(f"\nStable core — wards in ALL FOUR allocations ({len(stable_core)}):")
    for lga, w in sorted(stable_core):
        print(f"  {lga} / {w}")

    # Save the comparison as one CSV
    rows = []
    for name, alloc in allocations.items():
        for _, r in alloc.iterrows():
            rows.append(
                {"weighting": name, "lganame": r.lganame, "wardname": r.wardname, "channel": r.channel}
            )
    comp_df = pd.DataFrame(rows)
    comp_df.to_csv(SITING / "siting_weighting_comparison.csv", index=False)
    print(f"\nWrote {SITING / 'siting_weighting_comparison.csv'}")


if __name__ == "__main__":
    main()
