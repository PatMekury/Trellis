
# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent
"""Lock in the algorithmic baseline 25-node allocation, with community-first equity."""
from pathlib import Path
import pandas as pd
import geopandas as gpd
import shutil

DATA = (ROOT_DIR / "data")
SITING = DATA / "siting"
GPKG = DATA / "trellis_delta_wards.gpkg"
TMP_GPKG = "/tmp/trellis_delta_wards.gpkg"

LGA_QUOTAS = {
    "Warri South":      dict(phc=3, school=2, community=1),
    "Warri South-West": dict(phc=2, school=2, community=1),
    "Bomadi":           dict(phc=2, school=2, community=1),
    "Burutu":           dict(phc=2, school=2, community=1),
    "Patani":           dict(phc=1, school=2, community=1),
}
WEIGHTS = dict(child=0.35, no2=0.25, flare=0.15, coverage_gap=0.25)


def norm01(s):
    s = pd.Series(s).astype(float)
    if s.max() == s.min(): return s * 0
    return (s - s.min()) / (s.max() - s.min())


def main():
    df = pd.read_csv(SITING / "ward_siting_scores.csv")
    df["no2_for_score"] = df["no2_umol_m2_mean"]
    lga_mean = df.groupby("lganame")["no2_umol_m2_mean"].transform("mean")
    df["no2_for_score"] = df["no2_for_score"].fillna(lga_mean)

    cap = df["phc_per_1k_u5"].quantile(0.95)
    df["score"] = (
        WEIGHTS["child"] * norm01(df["pop_under5"]) +
        WEIGHTS["no2"] * norm01(df["no2_for_score"]) +
        WEIGHTS["flare"] * norm01(df["flare_total_bcm_13yr"]) +
        WEIGHTS["coverage_gap"] * (1 - norm01(df["phc_per_1k_u5"].clip(upper=cap)))
    ).round(3)

    selected = []
    used = set()
    for lga, q in LGA_QUOTAS.items():
        sub = df[df.lganame == lga].sort_values("score", ascending=False)

        # 1. PHC: needs facility host
        chosen_phc = []
        for _, r in sub[sub.fac_phc >= 1].iterrows():
            key = (r.lganame, r.wardname)
            if key in used: continue
            chosen_phc.append(r); used.add(key)
            if len(chosen_phc) >= q["phc"]: break

        # 2. Community FIRST: zero-facility wards get equity priority
        chosen_community = []
        zero_fac = sub[sub.fac_total == 0]
        for _, r in zero_fac.iterrows():
            key = (r.lganame, r.wardname)
            if key in used: continue
            chosen_community.append(r); used.add(key)
            if len(chosen_community) >= q["community"]: break
        for _, r in sub.iterrows():
            if len(chosen_community) >= q["community"]: break
            key = (r.lganame, r.wardname)
            if key in used: continue
            chosen_community.append(r); used.add(key)

        # 3. School: top remaining score
        chosen_school = []
        for _, r in sub.iterrows():
            key = (r.lganame, r.wardname)
            if key in used: continue
            chosen_school.append(r); used.add(key)
            if len(chosen_school) >= q["school"]: break

        for r in chosen_phc:        selected.append({**r.to_dict(), "channel": "PHC"})
        for r in chosen_community:  selected.append({**r.to_dict(), "channel": "community"})
        for r in chosen_school:     selected.append({**r.to_dict(), "channel": "school"})

    alloc = pd.DataFrame(selected)
    channel_order = {"PHC":0, "school":1, "community":2}
    alloc["co"] = alloc.channel.map(channel_order)
    alloc = alloc.sort_values(["co","lganame","score"], ascending=[True, True, False]).drop(columns=["co"]).reset_index(drop=True)
    alloc["node_id"] = ["TR-" + str(i+1).zfill(2) for i in range(len(alloc))]

    comp = pd.read_csv(SITING / "siting_weighting_comparison.csv")
    sets = {w: set(zip(g.lganame, g.wardname)) for w, g in comp.groupby("weighting")}
    stable_core = set.intersection(*sets.values())
    alloc["stable_core"] = alloc.apply(
        lambda r: (r.lganame, r.wardname) in stable_core, axis=1)

    def rationale(r):
        bits = []
        rk = int(r["rank"])
        pop = int(r["pop_under5"])
        no2 = r["no2_umol_m2_mean"]
        flare = r["flare_total_bcm_13yr"]
        phc = int(r["fac_phc"])
        ch = r["channel"]
        if rk <= 5: bits.append("Rank " + str(rk) + " overall")
        else: bits.append("Rank " + str(rk))
        if pop >= 5000: bits.append(f"{pop:,} children under 5")
        elif pop == 0: bits.append("zero pop captured (mangrove)")
        else: bits.append(str(pop) + " u5")
        if pd.notna(no2) and no2 >= 25: bits.append(f"high NO2 ({no2:.1f} umol/m^2)")
        if flare >= 0.5: bits.append(f"heavy flare ({flare:.2f} BCM)")
        elif flare > 0: bits.append("flare exposure")
        if phc == 0: bits.append("zero PHCs (equity)")
        if ch == "PHC" and phc >= 1: bits.append(str(phc) + " PHCs to host")
        if r["stable_core"]: bits.append("stable across all weightings")
        return "; ".join(bits)

    alloc["rationale"] = alloc.apply(rationale, axis=1)

    out_cols = ["node_id","channel","lganame","wardname","rank","score",
                "pop_under5","no2_umol_m2_mean","fac_phc","fac_total",
                "flare_total_bcm_13yr","stable_core","rationale"]
    alloc[out_cols].to_csv(SITING / "sensor_allocation.csv", index=False)
    print(f"Wrote {SITING/'sensor_allocation.csv'}: {len(alloc)} nodes")
    print(f"  stable core: {alloc.stable_core.sum()} / 25")

    print("\nFINAL 25-NODE BASELINE ALLOCATION:")
    for ch in ("PHC","school","community"):
        sub = alloc[alloc.channel == ch]
        print(f"\n=== {ch} ({len(sub)}) ===")
        print(sub[["node_id","lganame","wardname","score","pop_under5","no2_umol_m2_mean","fac_phc","fac_total","stable_core"]].to_string(index=False))

    pilot = gpd.read_file(TMP_GPKG, layer="pilot_wards")
    sites = pilot.merge(alloc[out_cols], on=["lganame","wardname"], how="inner")
    sites_proj = sites.to_crs("EPSG:32632")
    sites["site_lon"] = sites_proj.geometry.centroid.to_crs("EPSG:4326").x
    sites["site_lat"] = sites_proj.geometry.centroid.to_crs("EPSG:4326").y
    sites.to_file(TMP_GPKG, layer="sensor_sites", driver="GPKG")
    shutil.copy2(TMP_GPKG, GPKG)
    print(f"\nUpdated 'sensor_sites' in {GPKG}")


if __name__ == "__main__":
    main()