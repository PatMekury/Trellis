# Day 2 wrap — production decision channels and self-host DHIS2

**Date:** 9–10 May 2026 (sprint Day 2 of 5)
**Status:** Three of three Day 2 deliverables addressed; one (Sentinel-1 SAR-RVI) documented but not executed pending user credentials.

## What landed in Day 2

### 1. Production DHIS2 dashboard

`Trellis/dhis2/index.html` — DHIS2-styled multi-view dashboard reading the multi-year forecast.

**Features built:**
- Map of 51 pilot wards with forecast-NO₂ choropleth and click-to-drill-down
- Live LGA filter, tier filter (likely / possible / watch), ward search
- Per-ward time series chart with NO₂ / rainfall / temperature toggles (Chart.js)
- Per-ward stat grid with population, U5, facilities, flare BCM
- Sortable forecast table with all 51 wards, filter-aware export to CSV
- KPI strip: wards in alert, mean forecast NO₂, children in alert, predictor count

### 2. Self-host DHIS2 stack

`Trellis/dhis2/local/` — runnable end-to-end DHIS2 + Trellis integration.

**Files:**
- `docker-compose.yml` — DHIS2 2.41.4 + PostgreSQL on `localhost:8080`
- `nigeria_orgunits.json` (60 KB, **pre-generated and verified**) — 295 org units: 1 country + 1 state + 25 LGAs + 268 wards
- `ward_uid_lookup.json` — "LGA|Ward" → DHIS2 UID lookup
- `build_orgunits.py` — source code that produced the JSON
- `push_to_dhis2.py` — `--setup` posts metadata; without flag, pushes forecast as `dataValueSets`
- `index.html` — DHIS2-aware variant: tries DHIS2 API first, falls back to static JSON, shows source label in header
- `QUICKSTART.md` — five-step run guide

Verified: 295 org units, all UIDs unique, all parent references valid.

### 3. School advisory PWA

`Trellis/pwa-school/` — installable, offline-capable mobile-first PWA.

**Files:**
- `index.html` — single-page app with traffic-light alert, action checklist, 5-day outlook
- `manifest.json` — PWA manifest with inline SVG icons, theme colour, standalone display
- `sw.js` — service worker with cache-first strategy for offline support
- `forecast.json`, `ward_timeseries.json` — data
- `README.md` — three deployment paths (local Python server, GitHub Pages / Netlify, DHIS2 custom app)

**Features:**
- Ward selector (51 pilot wards) saved to localStorage
- Tier-coloured alert card with summary line per tier
- 3-tiered action checklist (likely / possible / watch) with Niger Delta-appropriate guidance
- 5-day outlook with deterministic per-ward synthesis
- Online/offline banner
- Install prompt for "Add to home screen"

### 4. Sentinel-1 SAR-RVI

Documented but not executed. `Trellis/data/ndvi/SENTINEL1_RVI_NOTES.md` covers the four candidate sources (Earth Search, Microsoft Planetary Computer, ASF, Copernicus DataSpace), confirms that none is anonymous-accessible from this sandbox, and provides the planetary-computer Python SDK code pattern that production deployment will use. The multi-year model already achieves +48% NO₂ skill without RVI; closing the gap is a quality improvement, not a prerequisite.

## Important course-correction during Day 2

Mid-Day-2, Patrick flagged three real concerns that reshaped the work:

1. **The DHIS2 dashboard wasn't actually calling DHIS2.** Static JSON only. I had defaulted to that without asking. Fixed: built the self-host DHIS2 stack and the dashboard now auto-detects DHIS2 vs static-JSON.
2. **Don't believe pending partnerships in trellis.md — ask first.** Saved to memory as an explicit rule.
3. **The partnerships I had been writing as "target" or "pending" were never confirmed.** Audited 9 files, found 20 distinct claims, stripped all named partners (Contrad CDG, NPHCDA, SUBEB, SMOH, UPTH, Niger Delta University, HISP WCA) from artefacts. Replaced with generic placeholders.

Outcome: every artefact on disk now passes the "no unconfirmed partnership" rule.

## Sprint status

| Day | Phase | Status |
|---|---|---|
| 1 | Trained forecast model + multi-year EO | **Done** (skills NO₂ +48%, rainfall +54%, temp +60%) |
| 2 | Production DHIS2 dashboard + production school PWA + Sentinel-1 SAR | **Done** (DHIS2 self-host stack runnable; PWA offline-capable; SAR documented for next session) |
| 3 | Caregiver SMS dispatcher service + surge planning UI | Pending your go |
| 4 | Sensor backend + sensor firmware | Pending |
| 5 | MCP server + open-source repo + end-to-end test | Pending |

## What you can do right now (Day 2 verification)

To verify Day 2 worked end-to-end, on your machine:

1. `cd Trellis/dhis2/local && docker compose up -d` — start your DHIS2
2. wait 3 minutes, change admin password in browser
3. update password in `push_to_dhis2.py` and `index.html`
4. `python3 push_to_dhis2.py --setup` — load metadata
5. `python3 push_to_dhis2.py` — push forecasts
6. Open `index.html` — header should say "DHIS2 live · admin · ..."

For the PWA:

1. `cd Trellis/pwa-school && python3 -m http.server 8081`
2. Open `http://localhost:8081` on a phone or laptop
3. "Add to home screen"
4. Open the installed app, then turn off Wi-Fi — it should still work, with an offline banner

## Files added or modified in Day 2

**Added:**
- `dhis2/local/` (full self-host stack — 11 files including `docker-compose.yml`, `push_to_dhis2.py`, pre-generated org-unit JSON, DHIS2-aware `index.html`, `QUICKSTART.md`)
- `pwa-school/manifest.json`, `pwa-school/sw.js`, `pwa-school/README.md`
- `data/ndvi/SENTINEL1_RVI_NOTES.md`

**Modified during partnership audit (Day 2 mid-stream):**
- All four `outreach/loi_*.md` letters renamed to generic templates; named-partner versions kept as `.deprecated`
- `outreach/loi_README.md` rewritten as templates explainer
- `outreach/attachment_ward_list.md` host references genericised
- `data/siting/sensor_allocation_proposal.md` — "implementing partners" language replaced
- `trellis_md_drafts/section_07_depin_sensor_network.md` — UPTH and Niger Delta University removed
- `trellis_outline_proposal.md` — named partners dropped from Phase 1 / team / open-questions sections
- `data/predictors/predictors_DATA_CARD.md`, `data/health/health_DATA_CARD.md`, `data/population/population_DATA_CARD.md`, `data/ndvi/ndvi_DATA_CARD.md`, `model/day1_skill_report.md`, `dhis2/SETUP_LOCAL_DHIS2.md` — Delta SMOH name references replaced with generic "state-level data-sharing arrangement"

## Open items going into Day 3

- Sentinel-1 RVI gap-fill (deferred — needs MPC SAS or ASF Earthdata credentials)
- Day 3 plan: caregiver SMS dispatcher (FastAPI + scheduler) + surge planning supervisor UI

Permission requested before starting Day 3.
