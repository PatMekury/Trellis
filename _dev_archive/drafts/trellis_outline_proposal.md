# trellis.md — proposed outline and artefact map

**Date:** 9 May 2026
**Status:** Pre-EOI scaffolding. trellis.md does not yet exist as a file; this document proposes the structure and points each existing session artefact at the section it belongs in.

---

## Why this exists

Per project instructions, trellis.md is the master reference for the Trellis project — sixteen sections covering challenge framing through to open questions. This session produced a substantial body of supporting work (six data layers, joint predictor table, sensor-siting analysis, EOI section draft, four LoIs) that needs a single document to live inside. This outline is the proposed structure of that document.

The outline below uses the sixteen-section template implied by the project instructions. For each section it states (a) the purpose, (b) which existing artefacts feed it, (c) what is still missing.

---

## Section-by-section

### 1. Challenge framing

**Purpose:** what climate-health problem Trellis addresses; why now.

**Existing material:** none on disk yet. Will draw from UNICEF Venture Fund 2026 Climate Ventures REOI scope (priority Areas 2 and 3) and the Niger Delta health-outcomes literature.

**To write:** ~250 words anchoring on (a) the dual climate-health problem in West African oil regions, (b) UNICEF's stated priority intersection of early warning and healthcare readiness, (c) why the Niger Delta is the right test domain.

### 2. The Niger Delta problem

**Purpose:** specific epidemiological and environmental context.

**Existing material:** none yet — needs verifiable Nigeria-specific statistics. Per project guardrails, do not invent gas-flaring volumes, oil-spill counts, district under-5 mortality, school pupil counts, or asthma prevalence; verify each before it lands in the document.

**To write:** ~400 words. Some numbers Trellis has already established from open data: GGFR records 442 persistent flare sites across Delta State 2012–2024; 1,059 health facilities (518 public, 251 private, 290 unknown ownership); five candidate pilot LGAs hold ~6.5 million people (Delta State total) and the pilot subset ~700,000 with 109,000 children under five.

### 3. Solution overview (Trellis)

**Purpose:** one-paragraph summary of the platform.

**Existing material:** the trellis project description in `TRELLIS_INSTRUCTIONS.md` Section 1 is essentially this paragraph. Use it.

**To write:** lift the Section 1 description, add a line on UNICEF Areas 2 + 3 simultaneity.

### 4. Theory of change

**Purpose:** the input → output → outcome causal chain.

**Existing material:** none yet.

**To write:** ~250 words from EO + sensors → predictor table → forecast → four decision channels → behaviour change in caregivers, schools, PHCs, ministries. Belsky et al. (2019) is the methodological lineage anchor for the place-based determinants framing.

### 5. Methodology

**Purpose:** how Trellis goes from raw data to a 4-week forecast.

**Existing material:**
- `data/predictors/predictors_DATA_CARD.md` — full schema of the 36-column predictor table with provenance per column
- `data/predictors/build_predictors.py` — reproducible build script
- `data/predictors/add_lags.py` — lagged-climate covariate derivation

**To write:** ~400 words on the seven-of-eight predictor stack, the ward-month grain, the 4-week horizon, the 3-tier confidence assignment (likely / possible / watch), and the methodological lineage (Snow 1854; Wimberly EPIDEMIA / Ethiopia; Allegheny County Pediatric Asthma Study; Kurland 2021). Will need a short subsection on the planned model architecture once it is settled (likely ensemble of gradient-boosted trees + spatial smoothing).

### 6. EO data layers

**Purpose:** which satellites, products, frequencies.

**Existing material — extensive:**
- `data/no2/no2_baseline_DATA_CARD.md` — Sentinel-5P NO₂, 12 months, 76.5% ward coverage
- `data/no2/preview/no2_12mo_mean.png` and `no2_monthly_panel.png` — embedded figures
- `data/rainfall/rainfall_DATA_CARD.md` — CHIRPS v2.0, 12 months, 100% ward coverage
- `data/rainfall/preview/rainfall_monthly_panel.png` — embedded figure
- `data/temperature/temperature_DATA_CARD.md` — NASA POWER (MERRA-2 reanalysis), 12 months
- `data/flares/flares_DATA_CARD.md` — World Bank GGFR 2012–2024, 442 Delta sites
- `data/flares/preview/flares_pilot_overview.png` — embedded figure
- `data/ndvi/ndvi_DATA_CARD.md` — Sentinel-2 NDVI, partial (43.8%)

**To write:** ~500 words tying these into one narrative. The honest framing: six EO layers, all open data, no auth required. Sentinel-1, sentinel-3, MODIS LST, and VIIRS Nightfire are listed in trellis.md's intended stack but require credentials and remain on the to-do list.

### 7. The DePIN sensor network

**Purpose:** the 25-node hardware network.

**Existing material:**
- `data/siting/sensor_allocation_proposal.md` — full proposal with 25-node ward-level allocation
- `data/siting/sensor_allocation.csv` — node-by-node table
- `data/siting/preview/siting_overview.png` — locked allocation map
- `data/siting/preview/siting_weighting_comparison.png` — robustness check across four weightings
- `eoi_drafts/sensor_siting_section.md` — 252-word EOI-ready section ready to slot in

**To write:** combine the EOI section draft (Section 7 head) with hardware reference (AirGradient-derived) and the per-node site finalisation process. This is the most-complete chapter at end of session.

### 8. Decision-support outputs (the four channels)

**Purpose:** DHIS2 dashboard, school advisory page, caregiver SMS, surge planning.

**Existing material:** none of the channel mockups or wireframes were touched this session.

**To write:** ~400 words. Existing mockups for the school advisory page and DHIS2 dashboard live in the project's mockup library (referenced in TRELLIS_INSTRUCTIONS.md Section 5). The SMS template, the pollution-to-child-health diagram, and the technical architecture diagram are listed there as not-yet-built.

### 9. Open-source architecture

**Purpose:** the code/data/hardware licensing stance.

**Existing material:** TRELLIS_INSTRUCTIONS.md Section 7 quick-reference table specifies: MIT (software), GPL (DHIS2 connectors), CC-BY (data and docs), TAPR Open Hardware (sensors).

**To write:** ~150 words. Add the GitHub repo URL once the repository is created and made public.

### 10. The pilot

**Purpose:** what Phase 1 looks like on the ground in Delta State.

**Existing material:**
- `data/trellis_delta_wards.gpkg` — ward boundaries, all data layers as GeoPackage layers
- `data/trellis_delta_wards_DATA_CARD.md` — boundary file documentation
- `data/health/delta_ward_facility_summary.csv` — 1,059 Delta health facilities, 51 pilot wards mapped
- `data/health/health_DATA_CARD.md`
- `data/population/population_DATA_CARD.md` — 700,000 pilot residents, 109,000 children under 5
- `outreach/` — four LoIs and a shared ward-list attachment

**To write:** ~400 words. The five LGAs (Warri South, Warri South-West, Burutu, Bomadi, Patani) need character paragraphs anchored on the population and exposure stats now on disk. Three pilot wards have zero health facilities (Akpakpa, Akugbene 2, Patani 2) — the equity argument should be made here.

### 11. Innovation principles alignment

**Purpose:** UNICEF Innovation Principles checklist response.

**Existing material:** none yet.

**To write:** ~250 words. Each of the nine UNICEF Innovation Principles gets one or two sentences mapping to a Trellis component. Open data, open hardware, locally-built (Nigerian incorporation), child-centric, and partnership-first are the natural strong points.

### 12. Three primary novelty levers

**Purpose:** what is genuinely new about Trellis vs prior art.

**Existing material:** TRELLIS_INSTRUCTIONS.md Section 7 names the three: (1) sub-district resolution via satellite + DePIN fusion; (2) cross-domain Niger-Delta-specific EO stack; (3) open MCP server architecture.

**To write:** ~250 words. For each lever, name the prior art (EWARS for #1, EPIDEMIA for #2, custom dashboards for #3) and the specific Trellis difference. The artefacts produced this session — particularly the joint predictor table at ward × month resolution combining seven open-data layers and the open siting analysis — are the empirical evidence for lever #1 and #2.

### 13. Phased roadmap

**Purpose:** Phase 1 (months 0–4), Phase 2 (months 4–9), Phase 3 (months 9–14).

**Existing material:** none on disk yet, but the LoI README implicitly sketches the Phase 1 partnership-development sequence.

**To write:** ~400 words. Phase 1 deliverables now include: GitHub repo public; ward boundary, NO₂, rainfall, temperature, flare, facility, population, NDVI layers all uploaded with data cards; sensor allocation locked; outreach commenced toward institutional partners (none currently engaged); incorporation status to be settled.

### 14. Budget

**Purpose:** $100k allocation framework.

**Existing material:** TRELLIS_INSTRUCTIONS.md Section 7 names $100,000 from UNICEF Venture Fund 2026 Climate Ventures.

**To write:** ~250 words and a budget table. Hardware, partnerships, fellowships/staff, and contingency. Specific allocation is not yet settled per project instructions Section 2.

### 15. Team

**Purpose:** named people, named roles.

**Existing material:** none on disk yet. Per project instructions, co-PI selection and full team composition are still in flux.

**To write:** Patrick (lead, currently named). All other roles — co-PI, implementing community partner, academic calibration partner, state-level data partner — are open and not yet identified. Avoid placeholder names.

### 16. Open questions

**Purpose:** what trellis.md acknowledges is unsettled.

**Existing material:** none on disk yet, but the session has clarified several:

- Co-PI institutional affiliation
- Final 5-LGA pilot vs candidate-LGA reduction
- DHIS2 read-access scope and timing (depends on SMOH response)
- Hardware procurement path (build vs buy AirGradient-derived sensors)
- The 10-PHC vs 10-school vs 5-community split (affirmed by this session's siting analysis but reviewable)
- The 8th predictor (DHIS2 health outcomes) — date and scope of access

**To write:** ~250 words. Be honest about uncertainty.

---

## Suggested authoring order

If you write trellis.md from this outline, the order that minimises blocking is:

1. Sections 7 (sensor network), 6 (EO), 10 (pilot) — most material on disk, anchor the document
2. Section 5 (methodology) — depends on 6, anchors the rest
3. Sections 3, 4 (solution overview + theory of change) — short, follow from above
4. Sections 12, 11 (novelty levers + innovation principles) — argument layer
5. Section 13 (roadmap) — concrete deliverables
6. Sections 1, 2 (challenge framing + Niger Delta problem) — most external research
7. Sections 14, 15 (budget + team) — last because most depends on partnerships not yet confirmed
8. Sections 16 (open questions), 8 (decision channels), 9 (open source) — connective

Sections 7, 10, and the predictor-stack subsection of 5 can be drafted from existing artefacts in 30–60 minutes each. Sections 1, 2, 14, 15 will require external research and decisions that have not yet been made.

---

## What's missing that this outline cannot fill

Five things that will block trellis.md from being submission-ready, regardless of how much writing happens:

1. **Confirmed co-PI** — names a person trellis.md cannot yet name.
2. **Verified Niger-Delta-specific statistics** — gas-flaring volumes, district under-5 mortality, school pupil counts, asthma prevalence figures must each have a verifiable citation before they go into Section 2.
3. **DHIS2 data access path** — the eighth predictor and the data foundation for DHIS2-integrated decision channel.
4. **Final budget allocation** — how the $100K splits across hardware, fellowships, partnerships, contingency.
5. **At least one signed LoI from any real institutional partner** — none currently identified.

The session has produced enough material to write a strong draft of about 60% of trellis.md. The remaining 40% is partnership- and budget-dependent.
