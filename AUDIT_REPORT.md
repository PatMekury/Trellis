# Trellis judging-grade audit

**Date:** 10 May 2026
**Scope:** every directory and file produced across the 5-day sprint, evaluated as if a UNICEF Venture Fund reviewer, a peer technical evaluator, and an open-source contributor were each going to grade it.
**Bottom line:** the *narrative* and *capability* of the platform is strong. The *execution hygiene* has nine deal-breakers a reviewer will catch within thirty minutes of reading. They are all fixable in roughly one focused half-day of work, but they must be fixed before submission.

The issues below are ranked by how badly they hurt your standing. Severity-1 issues will materially lower a judge's score; severity-2 erode credibility; severity-3 are polish.

---

## Severity 1 — fix before submission

### S1-1. Backend HMAC verification is essentially a no-op

**File:** `backend/app.py` lines 248–262

```python
if os.getenv("TRELLIS_SKIP_HMAC") != "1":
    # ...
    sig_check = hashlib.sha256((x_signature + payload.sensor_id).encode()).hexdigest()
    if not sig_check:
        raise HTTPException(401, "bad signature")
```

`sig_check` is the SHA-256 of any non-empty string, which is always a 64-character hex string. `if not sig_check` therefore never fires. **The auth check accepts any non-empty `X-Signature` header value as valid.** A reviewer who reads this file will immediately see the comment "This is a simplified verification suitable for dev" and treat the entire security model as fictitious.

**Fix:** store the plaintext per-sensor secret in a separate table (or a KV store) at enrollment time, look it up by `sensor_id` in `/ingest`, and use `hmac.compare_digest(hmac.new(secret, body, sha256).hexdigest(), x_signature)`. The `verify_hmac()` helper at line 156 is already written but unused.

### S1-2. 27 Python files have hardcoded sandbox absolute paths

**Files affected:** every `build_*.py` script in `data/*/` directories, plus `backend/app.py`, `data/predictors/build_predictors.py`, `data/siting/*.py`, `data/predictors/add_lags.py`, etc.

**Example:** `backend/app.py` line 26:
```python
FORECAST_PATH = Path(os.getenv("FORECAST_PATH",
    "/sessions/practical-nifty-thompson/mnt/Trellis/mvp/forecast_may_2026.json"))
```

`/sessions/practical-nifty-thompson/...` is a sandbox path. **Anyone who clones the repo and runs the code gets `FileNotFoundError` immediately.** This is the single most damaging issue for "industrial standard"; a reviewer's first attempt to reproduce your numbers will fail at the first `python3 build_*.py`.

**Fix:** replace every absolute sandbox path with a relative path or a `Path(__file__).resolve().parents[N]` reference. The default values inside `os.getenv()` should be relative paths suitable for a fresh clone.

### S1-3. Zero unit or integration tests

**Files affected:** entire repo. There is no `tests/` directory, no `test_*.py` file, no `__test__.cpp`. The CI workflow at `.github/workflows/ci.yml` runs lint and a smoke test that boots the backend and curls `/`, which is not a test.

A reviewer evaluating "industrial standard" code expects to see `pytest`, `unittest`, or at minimum a pinned set of integration tests with assertions. None exist.

**Fix:** add `tests/` directories at minimum to:
- `backend/tests/test_ingest.py` — enrollment round-trip, HMAC verification, ward attribution, calibration application
- `sms/tests/test_dispatch.py` — enrollment uniqueness, dispatch idempotency, audit-log shape
- `model/tests/test_forecast.py` — predictor table shape, model training reproducibility, forecast schema
- `mcp/tests/test_tools.py` — each MCP tool's input schema validation and output shape

Even ten focused tests would change the picture.

### S1-4. Build artefacts committed despite .gitignore

**Files present that shouldn't be:**
- `backend/__pycache__/app.cpython-310.pyc`
- `backend/__pycache__/simulate_sensor.cpython-310.pyc`
- `data/__pycache__/build_no2_baseline.cpython-310.pyc`
- `sms/__pycache__/app.cpython-310.pyc`
- `data/flares/delta_flare_sites.gpkg-journal`
- `data/trellis_delta_wards.gpkg-journal`

The `.gitignore` lists `__pycache__/` and `*-journal` but the files are physically present. A reviewer running `git status` after a clone-and-run will see polluted output. **The presence of `.pyc` files in a public repo is the canonical signal that the maintainer doesn't run `git clean -fd`.**

**Fix:** delete these files before submission, then verify `git status` is clean.

### S1-5. Two predictor tables committed, both with "current" naming

**Files:**
- `data/predictors/trellis_ward_month_predictors.csv` (612 rows, the original 12-month table)
- `data/predictors/trellis_ward_month_predictors_multiyear.csv` (6,936 rows, the actual current table)

Both files are present. The README and skill report reference the multi-year file. The non-multi-year file is stale but undeleted. A reviewer reading `data/predictors/` sees two files and doesn't know which is canonical.

**Fix:** delete `trellis_ward_month_predictors.csv`. Keep only the multi-year file. Update any code that references the old name to point at the new one.

### S1-6. Stale "12-month" claims across five data cards

After the multi-year retrain, the data cards were not updated. Files claiming "12 months" or "May 2025 – April 2026" when the actual data is now multi-year:

| File | Stale claim |
|---|---|
| `data/no2/no2_baseline_DATA_CARD.md` | "12 months" — actually 91 months on disk |
| `data/rainfall/rainfall_DATA_CARD.md` | "12 months" — actually 136 months |
| `data/predictors/predictors_DATA_CARD.md` | "12 months × 51 wards = 612 rows" — actually 136 × 51 = 6,936 |
| `data/ndvi/ndvi_DATA_CARD.md` | "12 months × 51 wards × 76.5%" — partial; need to revise |
| `data/temperature/temperature_DATA_CARD.md` | "12 months" — actually 76 months |

A reviewer cross-checking the README ("91 monthly Sentinel-5P NO₂ TIFs") against any data card will notice the inconsistency immediately. **This makes the platform look like it was abandoned mid-revision.**

**Fix:** rewrite the time-window paragraphs in all five data cards to match the multi-year reality. Update the coverage tables.

### S1-7. Day 1 sprint wrap is missing from the project root

The wraps for days 2, 3, 4, 5 are at the project root (`day2_wrap.md`, etc.). Day 1's wrap is at `model/day1_skill_report.md` (a different name, in a different directory).

**Fix:** copy the report to `day1_wrap.md` at the root, or symlink it, so the five-day sprint reads as one consistent narrative.

### S1-8. Three `.deprecated` LoI files cluttering `outreach/`

`outreach/loi_contrad_cdg.md.deprecated`, `outreach/loi_education_board.md.deprecated`, `outreach/loi_nphcda.md.deprecated` are sitting in the active outreach directory. They contain the partnership claims you explicitly stripped. A reviewer looking at the directory will see them, open one, and find the very claims the README says have been removed.

**Fix:** move them to `outreach/_archived/` so they don't appear at first glance, or delete them entirely (the rewrites are already in place).

### S1-9. README claims a GitHub URL that doesn't exist

`README.md` line 30 mentions `github.com/trellis-platform/trellis` as the planned location. Multiple other docs reference this URL. The repo does not yet exist.

This isn't fatal — "(planned)" is repeated everywhere — but a judge clicking the URL gets a 404 page from GitHub, which sets a bad first impression.

**Fix:** either create an empty repo at that URL with the README pre-populated, OR drop all the URL references and replace with "this repository" or "Trellis project repo" without committing to a specific URL.

---

## Severity 2 — credibility erosion

### S2-1. Missing `LICENSE-DHIS2` (GPL) and `LICENSE-HARDWARE` (TAPR) files

The README's licensing table claims:
- DHIS2 connectors → GPL-3.0
- Sensor firmware → TAPR Open Hardware License

Neither license file is present. Only `LICENSE` (MIT) and `LICENSE-DATA` (CC-BY) exist. A claim of GPL coverage without the GPL text is a copyright sticking point an open-source reviewer will flag.

**Fix:** add `LICENSE-DHIS2` (full GPL-3.0 text) and `LICENSE-HARDWARE` (TAPR Open Hardware License v1.0 text) at the project root.

### S2-2. CDN scripts loaded without Subresource Integrity (SRI) hashes

`mvp/index.html`, `dhis2/index.html`, `dhis2/local/index.html` all load `leaflet.js` and `chart.js` from CDN URLs without `integrity="sha384-..."` attributes. A security-minded reviewer will flag this as a supply-chain risk: any compromise of unpkg or jsdelivr is a remote code execution path into the dashboard.

**Fix:** add SRI hashes to all CDN script tags. Take 2 minutes per file; standard practice.

### S2-3. Firmware references an unregistered domain

`firmware/src/main.cpp` line 27:
```cpp
String backendUrl = "https://backend.trellis.health/ingest";
```

`backend.trellis.health` is not a registered domain. The captive portal preserves this default; if a deployer doesn't override it, the firmware will boot, fail DNS resolution, and silently drop readings.

**Fix:** change the default to `http://localhost:8001/ingest` (clearly a development default) or to a placeholder like `https://YOUR-BACKEND-HERE/ingest` that forces the deployer to override.

### S2-4. The MCP server has not been runtime-verified

The MCP server's syntax is valid but its runtime behaviour was never tested in the sandbox because `pip install mcp` was not done. The `claude_desktop_config_snippet.json` is plausible but unverified.

**Fix:** run `pip install mcp httpx` and `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp/server.py` to confirm it responds. Add a test that does this in CI.

### S2-5. Dashboard tiers all show "watch" or "possible" for May 2026

`mvp/forecast_may_2026.json` has zero "likely" wards. This is correct for May (wet-season transition), but a reviewer opening the dashboard for the first time sees "0 wards likely" and may interpret this as "the model never fires the most-severe alert." Without context, that looks underwhelming.

**Fix:** in the model's `forecast_may2026.py`, add a dry-season month forecast (e.g. December 2025, which would have many "likely" wards from the Harmattan signal) and ship both forecasts in the MVP. Toggle between months in the dashboard. This shows the model in a high-signal regime as well as a low-signal regime.

### S2-6. Skill scores are all reported against persistence; no climatology baseline

The skill report says "+48% NO₂ skill vs persistence baseline." Persistence (predicting next-month = this-month) is a weak baseline for highly-seasonal data. A stronger comparison is climatology (predicting next-month = mean of same calendar month over prior years). The original training script attempted this but reported "n/a" because the 12-month window was insufficient.

With 91 months of data now on disk, climatology baselines are computable. **A reviewer will ask: "what's the skill against climatology?" and you don't currently have that number.** It will likely be lower than the persistence number; better to publish it honestly than be caught not having computed it.

**Fix:** retrain the model with a proper climatology baseline computed (group by calendar month, take prior-year same-month mean). Report both skill scores in the skill report.

### S2-7. Backend `simulate_sensor.py` doesn't actually verify HMAC

The simulator computes a real HMAC and sends the right header, but because the backend's HMAC check (S1-1) is broken, a "successful" simulation proves nothing about the auth flow. The end-to-end test report says "HMAC signing in simulator verified" — that's only true that the simulator computes one, not that the backend rejects bad ones.

**Fix:** after fixing S1-1, add a negative test: the simulator should also send a request with a deliberately wrong signature and assert it gets HTTP 401.

### S2-8. CI workflow references the backend at `backend.app:app`

`.github/workflows/ci.yml` line 31:
```yaml
uvicorn backend.app:app --port 8001 &
```

But `backend/app.py` lives in a sibling directory at the repo root, not inside a Python package. Without an `__init__.py` and a top-level `pyproject.toml` setting up the import path, `backend.app:app` will fail to import.

**Fix:** add `backend/__init__.py` and have CI `cd backend` before `uvicorn app:app`, OR set `PYTHONPATH=backend` in the workflow.

### S2-9. Outreach attachment still names the actual ward list

`outreach/attachment_ward_list.md` lists every specific ward by name (Ekurede, Ubeji, etc.) under section headings labelled "PHC-channel nodes (10) — host: a primary health centre to be identified during Phase 1." The intent (hosts not yet identified) is preserved, but a casual reader scanning the table sees the named wards and may incorrectly assume all the wards are confirmed deployment targets.

**Fix:** add a paragraph at the top making clear that **ward selection itself is provisional pending field validation** — the open-data score identifies them but a sensor's host site requires a partnership conversation that has not happened.

---

## Severity 3 — polish

### S3-1. The end-to-end test report claims more than it verified

`E2E_TEST_REPORT.md` says "All 9 integration checks passed." Six of those checks were file-existence tests, not true integration tests. Reword: "9 integration *file-shape* checks passed; runtime integration test deferred to user's machine pending Docker access."

### S3-2. The README architecture diagram could be a real image

Currently it's ASCII art. A real Mermaid diagram or SVG would render more cleanly on GitHub. Easy improvement.

### S3-3. `surge/index.html` localStorage notes don't sync between supervisors

This is acknowledged in the README as a deliberate placeholder. A reviewer will understand. Leave the wording as is, but add the note to the front-of-page UI ("Notes are saved to your browser only") to prevent supervisor confusion.

### S3-4. `sms/app.py` has a dispatch query parameter that controls policy

`POST /dispatch?only_changed=true&only_alert=true` is fine for development, but in production these should be defaults set in environment variables (or a config file), not URL-controlled. A misconfigured cron job could accidentally pass `only_changed=false` and re-blast every caregiver.

**Fix:** read both flags from env vars; the URL params can override but are clearly logged.

### S3-5. NDVI data card claims partial coverage that has been partially fixed

After the multi-year retrain, the joint predictor table has NDVI from the annual composite broadcast across all months. The data card still says "Combined coverage 43.8%." That coverage is now 100% (the annual is broadcast).

**Fix:** rewrite the NDVI data card's coverage paragraph.

### S3-6. The 25-sensor BoM cost ($250 / unit) is unverified

`trellis_md_drafts/section_07_depin_sensor_network.md` line 9: "Total bill of materials sits at approximately $250 per node at one-off pricing." This number is plausible for the AirGradient base + a Sentec NO₂ cell + BME280 but has no actual vendor quote. If a UNICEF reviewer asks for a quote, you don't have one.

**Fix:** either pull a real vendor quote (AirGradient + Mouser/Digikey) and put the actual number in the doc, or qualify with "estimated" and a citation to a published BoM.

### S3-7. Several files include `Optional[...]` imports that may fail in some Pydantic configurations

`backend/app.py`, `sms/app.py` use `Optional[int]`, `Optional[str]` etc. but only `from typing import Optional` is imported. This is correct but Pydantic v2 sometimes prefers `int | None` syntax. Not broken, but inconsistent across files.

---

## What's actually strong

For balance, the things a reviewer will reach for and find solid:

- **Multi-year EO acquisition is genuine.** 91 months of Sentinel-5P, 136 months of CHIRPS, 76 months of NASA POWER all on disk and reproducible from the build scripts. This is the rare project where the "open data" claim is backed by file evidence.
- **Skill scores are honest.** +48% / +54% / +60% vs persistence is a real number from real walk-forward CV, not a marketing fabrication. The skill report names the baseline used.
- **The siting analysis is uniquely defensible.** The four-weighting robustness check that produces a 14-ward stable core is exactly the kind of rigour UNICEF reviewers reward.
- **Equity-flagged wards (Akpakpa, Akugbene 2, Patani 2) are in the stable core.** This is a meaningful structural claim.
- **The MCP server is genuinely novel.** Most climate-health platforms expose dashboards; few expose themselves as agent tools. This separates Trellis from the comparable WHO EWARS / EPIDEMIA prior art.
- **The DHIS2 self-host stack is end-to-end and runnable.** Most ministry-targeted platforms hand-wave DHIS2 integration; you have a full Docker-compose + metadata import + push script.
- **The partnership audit was actually applied.** This is rare integrity in pre-grant material.

## Recommended order of fix

If you have one half-day before submission:

1. **S1-2** (sandbox paths, ~90 min) — without this, no one can reproduce anything.
2. **S1-1** (HMAC, ~30 min) — security flaw a reviewer will catch.
3. **S1-4** (build artefacts, ~5 min) — `git clean -fd` then commit.
4. **S1-5** (duplicate predictor tables, ~5 min) — `rm` the stale one.
5. **S1-6** (stale "12-month" claims, ~45 min) — five data cards to update.
6. **S1-7** (Day 1 wrap, ~5 min) — `cp model/day1_skill_report.md day1_wrap.md`.
7. **S1-8** (deprecated LoIs, ~5 min) — move to `_archived/`.
8. **S2-1** (missing license files, ~10 min) — paste in the GPL-3.0 and TAPR text.
9. **S2-3** (firmware unregistered domain, ~2 min) — change default URL.
10. **S1-3** (zero tests, ~2 hours) — minimum 5 tests covering the critical paths.
11. **S1-9** (GitHub URL, ~5 min) — create the empty repo or drop the URL.

Total: about 4–5 focused hours. After that, the platform's narrative survives the technical scrutiny.

If you have two half-days, also fix S2-5 through S2-9.

If you have an additional day, also S2-2 (SRI hashes) and S2-6 (climatology baseline).

Severity-3 items are visible to attentive reviewers but not deal-breakers. Fix when convenient.

## A note on tone

Many of the user-facing READMEs read as "honest" rather than "professional." This is correct for an open-source project at pre-launch stage: hand-waving sells, but it doesn't get past Phase 1 review. The candour is a strength. Keep it. Don't be tempted to add marketing register before submission. The judging panels you're aiming for reward signal over polish.
