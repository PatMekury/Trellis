# Section 7. The DePIN sensor network

*Draft for trellis.md. Approximately 620 words excluding figure caption. Tone follows project guidelines: direct, professional, no marketing register.*

---

Trellis is built around a 25-node ground-truth sensor network. Each node measures the variables that matter at the height a child breathes — particulate matter, NO₂, ambient temperature, and humidity — at a fixed location, every minute, twenty-four hours a day. The network exists for three reasons. First, satellite NO₂ retrievals miss the smallest wards in the pilot domain (12 of 51 fall below the 5.5 × 3.5 km TROPOMI footprint and have no satellite signal at all in any month of 2025–2026). Second, satellite column density is not the same physical quantity as breathing-height surface concentration; the platform's exposure claims need a calibrated translation between the two. Third, ground sensors are the only way to detect transient single-flare plumes that do not last long enough or rise high enough to register in a satellite swath.

**Hardware.** Sensor nodes are built around the AirGradient open-hardware reference design, which the AirGradient project publishes under TAPR Open Hardware License. The Trellis configuration extends the reference with a Sentec NO₂ electrochemical cell and a Bosch BME280 environmental sensor. Each node logs locally and transmits over either GSM (urban wards) or LoRa-to-gateway (riverine wards). Power draw is under 2 W, allowing a small solar plus battery stack at sites without mains. Total bill of materials sits at approximately $250 per node at one-off pricing; lot-sized procurement is expected to drop this to under $200.

**Network siting.** The 25 nodes are split 10 PHC + 10 school + 5 community. Allocation is driven by a transparent composite ward score weighting child population (35%), Sentinel-5P NO₂ exposure (25%), health-coverage gap (25%), and persistent gas-flare volume (15%). All inputs are open data; the score is reproducible from a fifty-line Python script. Robustness was verified by re-running the allocation under three alternative weightings (child-only, exposure-only, equity-only): fourteen of the twenty-five proposed ward placements are unchanged, and the eleven that shift do so modestly. The three pilot wards with zero health facilities (Akpakpa, Akugbene 2, Patani 2) are in the stable core and assigned to the community channel; the equity guard is structural, not negotiated.

The flagship demonstration node is at Ekurede in Warri South: rank 1 by composite score, with 12,247 children under five, the second-highest tropospheric NO₂ in the pilot domain (29 μmol/m²), and 11 PHCs available to host. Co-located school and community nodes in adjacent wards permit ground-to-satellite cross-calibration from the first month of operation.

**Calibration.** Each Trellis node ships from the factory with a multi-point laboratory calibration against NIST-traceable reference standards for PM₂.₅ and NO₂. After deployment, in-situ co-location with one mobile reference instrument per LGA, loaned for a four-week shakedown period from an academic calibration partner to be identified, provides a field correction. The calibrated nodes then become the reference layer against which Sentinel-5P and Sentinel-3 retrievals are bias-corrected per ward, closing the column-to-surface gap that limits satellite-only platforms.

**Open-hardware commitment.** Build files, firmware, and the cross-calibration pipeline ship under the same TAPR Open Hardware License as the AirGradient base. Any other Niger Delta state — or any other oil-bearing region facing the same exposure-and-coverage problem — can re-build the network from the open files. This is the project's deliberate counter to the closed-hardware monitoring solutions that have to date dominated industrial-pollution monitoring in oil-producing countries.

**Figure 7.1.** *Locked sensor allocation across the five Delta State pilot LGAs.* Twenty-five nodes (10 PHC + 10 school + 5 community) over 51 candidate wards; thick black borders mark the fourteen wards that are stable across four alternative weighting schemes. (Source: `data/siting/preview/siting_overview.png`.)

---

## Word count and structure notes

- **Total words:** approximately 620 (excluding figure caption).
- **Paragraphs:** 7. Each paragraph is bounded with a clear single claim; consistent with the trellis.md house style.
- **Sub-headings used:** Hardware, Network siting, Calibration, Open-hardware commitment. Sentence-case, project-style.
- **External claims requiring verification before submission:**
  - "Total bill of materials approximately $250 per node at one-off pricing." — needs a current vendor quote on the modified AirGradient config.
  - "Approximately $200 at lot-sized procurement." — same.
  - The Sentec NO₂ electrochemical cell and Bosch BME280 are placeholders for the eventual chosen sensor units; final BoM will be settled in Phase 1.
  - The academic calibration loaner partner has not been identified.
- **Word count target:** the trellis.md house style suggests ~500–700 words per major section. This sits in the middle.

## What this section does NOT do

- Does not specify a particulate matter (PM) data card or a 12-month PM baseline. PM is not yet in the predictor table; the sensor network is the platform's only PM source. trellis.md will need a separate paragraph in Section 6 (EO) noting that PM is sensor-network-derived rather than satellite-derived.
- Does not name the specific PHC, school, or community building per node — that is explicitly a Phase 1 partner-led decision.
- Does not commit to a fixed deployment date — that depends on UNICEF Venture Fund acceptance and CAC incorporation completion.

## Linked artefacts on disk (do not re-list in trellis.md, but cite in the appendix)

- `data/siting/sensor_allocation.csv` — the 25-node table
- `data/siting/sensor_allocation_proposal.md` — the long-form proposal
- `data/siting/score_siting.py`, `lock_baseline.py`, `compare_weights.py` — reproducible scripts
- `data/siting/siting_weighting_comparison.csv` — robustness check table
- `data/siting/preview/siting_overview.png` — Figure 7.1
- `data/siting/preview/siting_weighting_comparison.png` — supporting four-panel robustness map (could go in an appendix)
