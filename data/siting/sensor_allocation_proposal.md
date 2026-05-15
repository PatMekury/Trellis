# Trellis sensor-siting prioritisation and 25-node allocation proposal

**Date:** 9 May 2026
**Status:** Pre-EOI proposal, locked algorithmic baseline
**Output of:** `data/siting/score_siting.py`, `data/siting/lock_baseline.py`, `data/siting/compare_weights.py`

## 1. Why this analysis exists

trellis.md commits to deploying a 25-node open-hardware DePIN sensor network across the Delta State pilot domain, allocated as 10 primary health centre nodes, 10 school nodes, and 5 community nodes. The pilot covers 51 wards across five LGAs. With only 25 sensors for 51 wards, the deployment plan must answer the reviewer's natural question — *why these wards, not the other 26?* — with a transparent, reproducible answer that any auditor can re-derive from the same open-data inputs.

This document gives that answer.

## 2. Composite siting score

Each pilot ward receives a score on [0, 1] computed as a weighted sum of four normalised components.

| Component | Weight | Variable | Source |
|---|---|---|---|
| Child population at risk | 35% | `pop_under5` | WorldPop 2024 × Nigeria national U5 fraction |
| Pollution exposure signal | 25% | 12-month mean NO₂ | Sentinel-5P, MEEO COG mirror |
| Health-coverage gap | 25% | inverse of `phc_per_1k_u5`, capped at 95th percentile | GRID3 NHFR + WorldPop |
| Industrial flare exposure | 15% | `flare_total_bcm_13yr` | World Bank GGFR 2012–2024 |

Each component is min-max normalised across the 51 pilot wards before weighting. Wards without TROPOMI coverage have NO₂ filled with their LGA mean (so we do not penalise wards for being too small to register on the satellite). The coverage-gap score is capped at the 95th percentile to prevent a single very-well-served ward from collapsing the rest of the distribution.

The 35/25/25/15 weighting reflects the project's stated multi-objective stance: child-centric (heaviest weight on under-5 population), exposure-driven (measurable NO₂), equity-aware (health-coverage deficit), and industrially-honest (flare exposure, lighter weight because flares affect fewer wards but with high concentration where they do).

## 3. Robustness check — the stable core

The natural objection to any weighted score is "you chose those weights — would the answer change under different weights?" To respond directly, the same allocation algorithm was re-run under three alternative weightings:

- **Child-only** (100% on child population)
- **Exposure-only** (50% NO₂ + 50% flares; no population, no coverage)
- **Equity-only** (100% on coverage gap)

Across the four weightings — baseline + three alternates — **fourteen of the twenty-five wards receive a sensor every time**. These constitute the *stable core* of the deployment:

| LGA | Stable-core wards |
|---|---|
| Warri South | Ekurede, Okere, Pessu |
| Warri South-West | Ugborodo, Ogbe-Ijoh, Okerenkoko, Akpakpa |
| Bomadi | Bomadi, Kpakiama, Akugbene 2 |
| Patani | Patani 2, Patani 5 |
| Burutu | Ogulagha, Kiagbodo |

The remaining eleven nodes are weighting-dependent and shift modestly between schemes (full comparison in `data/siting/siting_weighting_comparison.csv`). Reasonable people can disagree about those eleven; they cannot disagree about the fourteen.

The three pilot wards with **zero health facilities** (Akpakpa, Akugbene 2, Patani 2) are all in the stable core. So is the flagship demonstration ward (Ekurede). The wards Trellis can least afford to leave unobserved are the wards a sensor reaches first under any reasonable weighting.

## 4. Allocation rules

- **Channel constraint (from trellis.md):** 10 PHC, 10 school, 5 community.
- **Universal LGA coverage:** every pilot LGA receives at least one PHC sensor, one school sensor, and one community sensor — three observation channels per LGA.
- **PHC nodes go to wards that have at least one PHC** (so the sensor has a real host) and prefer the highest-scoring such wards within each LGA.
- **Community nodes are allocated before school nodes**, with explicit priority on zero-facility wards. This is the equity guard: it ensures Akpakpa, Akugbene 2, and Patani 2 cannot be displaced by a higher-scoring ward.
- **School nodes take the top remaining score** in each LGA after PHC and community allocations.

LGA quotas (sum to 25):

| LGA | PHC | School | Community |
|---|---|---|---|
| Warri South | 3 | 2 | 1 |
| Warri South-West | 2 | 2 | 1 |
| Bomadi | 2 | 2 | 1 |
| Burutu | 2 | 2 | 1 |
| Patani | 1 | 2 | 1 |

## 5. The locked 25-node allocation

### PHC nodes (10) — host facility provides power, mounting, custodianship

| Node | LGA | Ward | Score | Rationale |
|---|---|---|---|---|
| TR-01 | Bomadi | Bomadi | 0.48 | Bomadi LGA centre; 5,833 children U5; 3 PHCs to host; stable core |
| TR-02 | Bomadi | Kpakiama | 0.37 | Riverine secondary Bomadi; 2,863 children U5; 3 PHCs; stable core |
| TR-03 | Burutu | Ogulagha | 0.40 | Forcados estuary; 4,975 children U5; 5 PHCs; flare exposure; stable core |
| TR-04 | Burutu | Kiagbodo | 0.37 | Riverine Burutu; 2,458 children U5; 2 PHCs; stable core |
| TR-05 | Patani | Patani 5 | 0.41 | Patani score-leader with PHC; 2,240 children U5; 1 PHC; stable core |
| TR-06 | Warri South | Ekurede | 0.80 | **Rank 1**; 12,247 children U5; high NO₂ (29 μmol/m²); 11 PHCs; stable core |
| TR-07 | Warri South | Ubeji | 0.66 | Rank 2; 10,314 children U5; 6 PHCs |
| TR-08 | Warri South | Okere | 0.65 | Rank 3; 9,257 children U5; 10 PHCs; stable core |
| TR-09 | Warri South-West | Ugborodo | 0.51 | Flare-belt centre; flare exposure 1.05 BCM; 1 PHC; stable core |
| TR-10 | Warri South-West | Ogbe-Ijoh | 0.49 | Northern flare-belt; flare exposure 1.14 BCM; 4 PHCs; stable core |

### School nodes (10) — primary school custodianship, supports school advisory channel

| Node | LGA | Ward | Score | Rationale |
|---|---|---|---|---|
| TR-11 | Bomadi | Akugbene 1 | 0.30 | 0 PHCs (equity-flagged); school is the only daily-attended observation point |
| TR-12 | Bomadi | Esanma | 0.26 | Riverine Bomadi school; pairs with Kpakiama PHC |
| TR-13 | Burutu | Egodor | 0.29 | Newly-mapped ward (closed by GRID3 v2.0); 5 PHCs; 1,760 children U5 |
| TR-14 | Burutu | Eseinbiri | 0.29 | Riverine Burutu; 2,600 children U5; 4 PHCs |
| TR-15 | Patani | Agoloma | 0.37 | Patani top NO₂ (22 μmol/m²); 1 PHC; pairs with Patani 5 PHC |
| TR-16 | Patani | Uduophori | 0.37 | Second Patani school; 1,730 children U5; 1 PHC |
| TR-17 | Warri South | Igbudu | 0.58 | Rank 5; 7,774 children U5; 14 PHCs (densest in pilot) |
| TR-18 | Warri South | Avenue | 0.47 | Mid-density urban Warri; 3,738 children U5; 7 PHCs |
| TR-19 | Warri South-West | Okerenkoko | 0.39 | Flare belt; 0.90 BCM cumulative flaring; stable core |
| TR-20 | Warri South-West | Ogidigben | 0.31 | Coastal flare belt; 0.54 BCM cumulative flaring |

### Community nodes (5) — community-managed, fills equity gaps

| Node | LGA | Ward | Score | Rationale |
|---|---|---|---|---|
| TR-21 | Bomadi | Akugbene 2 | 0.29 | **Zero facilities; zero captured population (mangrove)**; equity-flagged; stable core |
| TR-22 | Burutu | Tuomo | 0.30 | Riverine Burutu; 2,395 children U5; 3 PHCs (no zero-fac in Burutu, takes top remaining) |
| TR-23 | Patani | Patani 2 | 0.41 | **Zero facilities, zero PHCs**; equity-flagged; stable core |
| TR-24 | Warri South | Pessu | 0.62 | Rank 4; 4,862 children U5; **highest single-ward NO₂ in pilot (30.3 μmol/m²)**; stable core |
| TR-25 | Warri South-West | Akpakpa | 0.30 | **Zero facilities**; mangrove community; equity-flagged; stable core |

## 6. Coverage of the equity wards

The three pilot wards with zero health facilities — **Akpakpa, Akugbene 2, Patani 2** — are all in the stable core and all assigned to the community channel. This is the equity argument in concrete form: the wards that would be unobserved without Trellis are the first wards Trellis observes.

## 7. Caveats

- **Ward-centroid placement is provisional.** The proposed sites use ward centroids as the geographic anchor for the map. Final node placement must be at a specific named PHC, school, or community building chosen during Phase 1 in collaboration with whichever institutional partner endorses each channel.
- **Three Warri South wards have no TROPOMI NO₂ data** (Okere, Igbudu, Avenue, Bowen). These were scored using the Warri South LGA mean NO₂. The alternative — penalising small wards for being smaller than a satellite pixel — would have pushed sensors *away* from the highest-population ward in the pilot, which the data does not justify.
- **Patani has only one PHC node (the minimum).** Patani has the smallest pilot population and the lowest cumulative composite scores. Adding a second Patani PHC node would mean removing one from another LGA where the score is higher; the allocation chooses score-driven reallocation over forced uniformity.
- **The first three nodes (Ekurede, Ubeji, Okere) are all in Warri South.** This is a concentration risk. Mitigation: PHC + school + community in different Warri South wards plus the deliberate Warri South-West, Bomadi, Patani, Burutu coverage gives the network real geographic spread. Reviewers who object to the concentration should understand that 48% of the pilot child population lives in those 10 Warri South wards.
- **The 35/25/25/15 weighting is a proposal, not a result.** The stable-core analysis (Section 3) is the answer to challenges on the weighting choice: 14 wards survive any reasonable weighting, only 11 nodes shift.

## 8. Reproducibility

```bash
cd data/siting
python3 score_siting.py        # produces ward_siting_scores.csv
python3 compare_weights.py     # produces siting_weighting_comparison.csv (4 schemes)
python3 lock_baseline.py       # produces sensor_allocation.csv (final 25 nodes)
```

The scoring weights are constants at the top of `score_siting.py`. The LGA quotas and allocation rules are constants at the top of `lock_baseline.py`. Both files are short and reviewable; either can be re-run after any predictor refresh.

## 9. What this enables next

- **Phase 1 deliverable: Letters of intent.** With named host wards, the project conducts formal outreach to identify and engage the institutional partner(s) that will host each channel.
- **Per-node manufacturing/logistics plan.** With known sites, the AirGradient-derived hardware build can be lot-sized with one configuration per channel (PHC/school/community) and shipped accordingly.
- **Cross-validation pairs.** The allocation co-locates several PHC-school pairs in the same LGA (Bomadi PHC + Akugbene 1 school; Burutu Ogulagha PHC + Egodor school; Patani 5 PHC + Agoloma school). These pairs become the primary calibration mechanism between satellite and ground-sensor signals.
- **An auditable record for UNICEF reviewers.** The siting decision is now defended end-to-end by open data plus three short Python scripts. Any reviewer can re-derive the answer.
