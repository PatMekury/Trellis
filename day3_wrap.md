# Day 3 wrap — caregiver SMS dispatcher and surge planning UI

**Date:** 10 May 2026 (sprint Day 3 of 5)
**Status:** Both Day 3 deliverables built and verified.

## What landed

### 1. Caregiver SMS dispatcher service — `Trellis/sms/`

FastAPI service that takes the Trellis 4-week forecast and sends an SMS alert to enrolled caregivers when their ward's air-quality tier changes.

**Files:**
- `app.py` — FastAPI service with 7 endpoints (root, forecast, enroll, enrollments, dispatch, audit, unenroll)
- `requirements.txt` — fastapi, uvicorn, pydantic
- `Dockerfile` — Python 3.11-slim container
- `docker-compose.yml` — single-service compose with provider env vars
- `README.md` — endpoint reference + provider notes

**Architecture:**
- SQLite for enrollment + audit log + last-tier-per-ward state
- Pluggable SMS provider abstraction with three concrete adapters: `MockProvider` (logs to stdout), `AfricasTalkingProvider` (the standard Nigerian gateway), `TwilioProvider` (international fallback)
- Two language templates: English (`en`) and Nigerian Pidgin (`pcm`), each with three tier variants (likely / possible / watch)
- Each rendered message fits under the 160-character single-SMS limit

**Verified end-to-end:**
- Three enrollments accepted across three different wards and two languages
- Dispatch sent three messages via the mock provider, audit logged correctly with provider response
- Re-dispatch correctly skipped all three when tiers had not changed (idempotency)

### 2. Primary care surge planning UI — `Trellis/surge/`

Single-page web app for PHC supervisors. Reads the same forecast as the DHIS2 dashboard but presents it in a workflow built around weekly staffing and stock decisions.

**Files:**
- `index.html` — full single-file SPA
- `forecast_may_2026.json`, `ward_timeseries.json` — the data
- `README.md` — usage + customisation notes

**Features:**
- KPI strip (top priority ward, alert count, exposed U5, PHC-equipped fraction)
- Ranked ward list with visual priority bar; sortable columns; filter by LGA / tier
- Per-ward detail card with forecast, climatology, suggested action, supervisor note (localStorage-backed)
- Weekly roster CSV export
- Print-optimised "morning brief" view, one block per LGA, ready to print and walk into the supervisor's morning meeting

**Priority score formula:**

`priority = forecast NO₂ × children-under-5 / 1000`

This collapses exposure dose and exposed population into a single number so the supervisor can see at a glance which wards are both high-exposure and high-population. Top wards by this measure are dominated by Warri South (large under-5 populations).

## Day 3 architectural choices worth flagging

### SMS dispatcher: idempotent + opt-in-friendly

The `dispatch` endpoint defaults to `only_changed=true` and `only_alert=true`. So calling it nightly does nothing if no tier changed — safe to schedule via cron with no risk of spamming caregivers. Tier changes are tracked per ward in a `last_tier` table.

### SMS dispatcher: provider abstraction

The provider class is a one-method interface (`send(phone, message) -> dict`). Adding a new provider (e.g. Wilio, MTN bulk API, or a custom gateway) is one new class. Setting `TRELLIS_SMS_PROVIDER=africas_talking` switches at runtime.

### Surge UI: localStorage notes are a deliberate placeholder

For a multi-supervisor or multi-device deployment, the notes need a backend. I left this as localStorage so the UI is self-contained and runnable today; the migration path is to swap the `localStorage.getItem` / `setItem` calls for `fetch` calls to a notes API.

### Surge UI: separate from the DHIS2 dashboard

The DHIS2 dashboard is for ministry-level analytics. The surge UI is for a PHC supervisor making this-week decisions. They share the same data layer but their workflows are different enough that one UI for both would compromise both. This matches the four-channel architecture in trellis.md.

## What this does NOT do (open for Day 4 / Day 5)

- **No two-way SMS.** Inbound replies aren't handled.
- **No opt-in handshake.** Currently the `/enroll` endpoint trusts the caller. Production needs a confirm-via-SMS double-opt-in.
- **No quiet hours.** Sends whenever `/dispatch` is called.
- **No staffing roster generation in surge UI.** Just produces a ranked ward list.
- **No real-time notifications in surge UI.** Polling only.

## Sprint status

| Day | Phase | Status |
|---|---|---|
| 1 | Trained forecast model + multi-year EO | Done (skill +48% NO₂) |
| 2 | Production decision channels + DHIS2 self-host | Done |
| 3 | Caregiver SMS dispatcher + surge planning UI | **Done** |
| 4 | Sensor backend + sensor firmware | Pending your go |
| 5 | MCP server + open-source repo + end-to-end test | Pending |

## Files added in Day 3

| Path | Lines | Purpose |
|---|---|---|
| `sms/app.py` | ~280 | FastAPI service |
| `sms/requirements.txt` | 5 | dependencies |
| `sms/Dockerfile` | 8 | container |
| `sms/docker-compose.yml` | 17 | compose config |
| `sms/README.md` | ~140 | endpoint reference |
| `surge/index.html` | ~340 | full SPA |
| `surge/README.md` | ~85 | usage + customisation |

Plus copied data files in each folder (~440 KB total).

## What you can verify on your machine

**SMS dispatcher:**
```bash
cd sms
pip install -r requirements.txt
cp ../mvp/forecast_may_2026.json forecast.json
uvicorn app:app --reload --port 8000
# In another terminal:
curl -X POST http://localhost:8000/enroll \
  -H "Content-Type: application/json" \
  -d '{"phone":"+2348011110001","lganame":"Warri South","wardname":"Ekurede","child_age_years":3,"lang":"en"}'
curl -X POST http://localhost:8000/dispatch
curl http://localhost:8000/audit
```

**Surge UI:**
```bash
cd surge
python3 -m http.server 8082
# Open http://localhost:8082
```

Per the permission rule, I am not starting Day 4 without your explicit go.
