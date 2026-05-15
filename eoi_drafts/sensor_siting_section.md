# Sensor network siting (EOI draft, ~250 words)

*Draft for the UNICEF Venture Fund 2026 Climate Ventures EOI. Written to slot into the methodology or pilot section of trellis.md. Tone matches the existing document — direct, professional, no marketing register.*

---

## Sensor network siting

Trellis deploys 25 open-hardware DePIN sensors across 51 wards in the five candidate Delta State pilot LGAs (Warri South, Warri South-West, Burutu, Bomadi, Patani): 10 nodes hosted at primary health centres, 10 at primary schools, and 5 at community sites. Allocation is driven by a transparent composite score per ward that weights child population at risk (35%), measurable pollution exposure from Sentinel-5P NO₂ (25%), health-coverage gap measured as PHCs per 1,000 children under five (25%), and persistent gas-flare exposure from the World Bank Global Gas Flaring Reduction dataset (15%). All inputs are open data; the score is reproducible from a fifty-line Python script.

The allocation is robust to the weighting choice. Under three alternative weightings — child-population only, exposure only, and equity only — fourteen of the twenty-five proposed ward placements are unchanged. The eleven that shift do so modestly. The three pilot wards with zero health facilities (Akpakpa in Warri South-West, Akugbene 2 in Bomadi, Patani 2 in Patani) are in this stable core and assigned to the community channel; the equity guard is structural, not negotiated.

The flagship demonstration node is at Ekurede in Warri South — rank 1 by composite score, with 12,247 children under five, the second-highest tropospheric NO₂ in the pilot domain (29 μmol/m²), and 11 PHCs available to host a sensor. Co-located school and community nodes in adjacent wards permit ground-to-satellite cross-calibration from the first month of operation.

**Figure (suggested placement):** *Trellis pilot LGAs: locked sensor-siting proposal* — the right-hand panel from `data/siting/preview/siting_overview.png`, showing 25 nodes coloured by channel with the 14 stable-core wards outlined in black.

---

## Word count

Approximately 252 words excluding the figure caption.

## Where it slots into trellis.md

This section belongs in the **DePIN sensor network** chapter (Section 7 in the current trellis.md table of contents), immediately after the hardware reference description (AirGradient-derived) and before the data-fusion methodology. It can also be referenced from the **Pilot** chapter as the deployment-allocation evidence base.

## Deliverable footprint

This single section is supported by the following artefacts already on disk in `data/`:

- `predictors/trellis_ward_month_predictors.csv` — 612 rows × 36 columns, the joint predictor table the score is derived from
- `siting/ward_siting_scores.csv` — per-ward composite scores
- `siting/siting_weighting_comparison.csv` — four-scheme weighting robustness check
- `siting/sensor_allocation.csv` — the locked 25-node allocation with rationales
- `siting/sensor_allocation_proposal.md` — the long-form proposal that this section condenses
- `siting/preview/siting_overview.png` — the embedded figure

A reviewer who challenges any number in this paragraph can re-derive it from those files.

## Optional 100-word ultra-condensed variant

For tight word budgets, the section compresses to:

> Trellis deploys 25 sensors across 51 pilot wards: 10 at PHCs, 10 at schools, 5 at community sites. A composite ward score weights child population (35%), Sentinel-5P NO₂ (25%), PHCs per child-under-five (25%), and GGFR flare volume (15%). Across four alternative weightings, fourteen of the twenty-five placements are unchanged — including all three pilot wards with zero health facilities, which are assigned to the community channel as a structural equity guard. The flagship demonstration node is at Ekurede in Warri South: 12,247 children, NO₂ rank 2 of 51, 11 PHCs to host. All inputs are open data; the allocation is reproducible from a single Python script.

That's 113 words.
