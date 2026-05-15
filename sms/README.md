# Trellis caregiver SMS dispatcher

FastAPI service that takes the Trellis 4-week forecast and sends an SMS alert to enrolled caregivers when the air-quality tier in their ward changes. Pluggable SMS provider with mock / Africa's Talking / Twilio adapters; SQLite-backed enrollment and audit log.

## Run it locally

```bash
cd sms
pip install -r requirements.txt
cp ../mvp/forecast_may_2026.json forecast.json
uvicorn app:app --reload --port 8000
```

Or with Docker:

```bash
cd sms
cp ../mvp/forecast_may_2026.json forecast.json
docker compose up -d
```

Service runs at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/docs`.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/` | Service info, provider name, endpoint list |
| GET | `/forecast` | Current loaded forecast (the same JSON the dashboard uses) |
| POST | `/enroll` | Register a caregiver: phone + ward + child age + language |
| GET | `/enrollments` | List enrollments, optionally filtered by LGA / ward |
| DELETE | `/enroll/{id}` | Unenroll |
| POST | `/dispatch` | Run a dispatch cycle. Sends to each enrolled caregiver per the policy: by default only when the ward's tier has *changed* since last send AND the new tier is not "watch". The optional `?channel=` parameter selects which advisory layer (default `general`; also `malaria` and `respiratory`). |
| GET | `/audit` | View send history (most recent first) |

## Configuration

Environment variables:

| Var | Default | Purpose |
|---|---|---|
| `TRELLIS_SMS_PROVIDER` | `mock` | One of `mock`, `africas_talking`, `twilio` |
| `TRELLIS_AT_USERNAME` | `sandbox` | Africa's Talking username |
| `TRELLIS_AT_API_KEY` | (none) | Africa's Talking API key |
| `TRELLIS_TWILIO_SID` | (none) | Twilio account SID |
| `TRELLIS_TWILIO_TOKEN` | (none) | Twilio auth token |
| `TRELLIS_TWILIO_FROM` | (none) | Twilio sender number |

## Message templates

Two languages built in:

- `en` (English, default) — formal / hospital-style register
- `pcm` (Nigerian Pidgin) — community register, shorter sentences

**Three template families** (one per `?channel=` value):

| Channel | Function | Tier source | Purpose |
|---|---|---|---|
| `general` | `render(tier, ward, lang)` | `forecast['tier']` | Generic environmental alert (existing behaviour) |
| `malaria` | `render_malaria(tier, ward, lang)` | `forecast['malaria_risk_tier']` | Malaria-specific advisory (rainfall + temperature thresholds, EPIDEMIA-aligned) — references ITN, RDT, fever screening |
| `respiratory` | `render_respiratory(tier, ward, lang, child_age_years)` | `forecast['tier']` | Toddler-asthma framing: under-5 indoor advisory at midday, inhaler reminder, paediatric-specific text. If `child_age_years <= 3` the message uses the word "toddler" instead of "child" |

Each template fits under the 160-char single-SMS limit.

Examples:

**General, English, likely:**
> TRELLIS ALERT: Ekurede. Air quality LIKELY to be poor next 2-4 weeks. Keep small children indoors mid-day. Watch for cough or fast breathing. Visit PHC if breathing fast. Free advice line: 1234.

**Malaria, English, likely:**
> TRELLIS MALARIA ALERT: Ekurede. Environmental conditions LIKELY for mosquito breeding next 2-4 weeks. Use ITN every night. If your child has fever, go to PHC for malaria test. Empty containers that hold water. Free advice line: 1234.

**Respiratory, English, likely (with toddler age 2):**
> TRELLIS RESPIRATORY ALERT: Ekurede. Forecast NO2 LIKELY elevated for under-5s next 2-4 weeks. Keep your toddler indoors during midday (11am-3pm). If your child has diagnosed asthma, follow their action plan; have reliever inhaler ready. Visit PHC immediately if wheeze or fast breathing does not settle. Free advice: 1234.

**Malaria, Pidgin, likely:**
> TRELLIS MALARIA WARN: Ekurede. Mosquito breeding fit high next 4 weeks. Sleep under net every night. If pikin get fever, go health centre to test. Don't keep stagnant water near house. Free advice: 1234.

The `last_tier` table is partitioned by `channel`, so a malaria-tier transition does not suppress a respiratory dispatch on the same ward (and vice-versa).

## How dispatch works

`POST /dispatch?only_changed=true&only_alert=true` (the defaults):

1. Load current forecast (51 wards × tier)
2. Look up the last tier sent per ward (in `last_tier` table)
3. For each enrolled caregiver, decide:
   - If their ward's current tier is `watch` and `only_alert=true`, skip
   - If the tier matches the last-sent tier and `only_changed=true`, skip
   - Otherwise render the message in the caregiver's language and send via the active provider
4. Log every send (sent or failed) to the `audit` table
5. Update `last_tier` for all 51 wards with the current forecast tiers

Schedule a daily cron / systemd timer / cloud scheduler to hit `/dispatch` at the desired time. The endpoint is idempotent for the "no change" case so re-running is safe.

## Provider notes

**Mock** is the default and writes to console. Use this for development.

**Africa's Talking** is the standard SMS gateway in Nigeria. Free sandbox at `https://account.africastalking.com/` delivers only to AT's Simulator app (not real phones). For real Nigerian carrier delivery you need a Team (production app), a topped-up wallet, and a generated API key — full walkthrough below.

**Twilio** is the international fallback. Free $15 trial credit at `https://www.twilio.com`. Phone numbers must be verified in trial mode.

### Setting up Africa's Talking for production (~10 minutes)

This walkthrough was tested end-to-end on 10 May 2026 against AT's current UI. Every step matters — skipping any one produces a confusing failure mode.

**Step 1 — Create an AT account.** Go to https://account.africastalking.com and sign up. Verify your email.

**Step 2 — Create a Team (production app context).** On the account home page you'll see two sections: **Sandbox** and **Teams**. Sandbox is free but delivers only to AT's simulator app — not what you want. Click **New Team** to create a production-ready context. Name it (e.g., "Trellis-pilot"), pick Nigeria as country, save. AT lands you on the team page.

**Step 3 — Create an App inside the Team.** Inside the Team, click **Create App**. Name it (e.g., "Trellis"). AT generates a unique **username** for the app (something like `trellisapp`) — this is the value that goes into `TRELLIS_AT_USERNAME`. Note it.

**Step 4 — Top up the wallet.** Inside the app, click **Billing** in the left sidebar → **Top Up**. Minimum is around $5 (₦8,000). Pay with Visa/Mastercard. Nigerian SMS costs ₦4 each — $5 covers ~2,000 messages, way more than test needs. *Tested fact:* you don't need to top up to $5 — even ₦100 (about $0.07) is enough for 25 test messages.

**Step 5 — Generate the API key.** Inside the app's sidebar: **Settings → API Key**. Enter your AT account login password. Click **Request**. AT emails you a one-time link within ~30 seconds. Click the link — the API key is shown ONCE on the page that loads. Copy it immediately. It begins with `atsk_` followed by a long hex string. This is the value for `TRELLIS_AT_API_KEY`.

> **The key is shown only once.** If you close that page without copying, you have to re-request from the same Settings → API Key page and AT generates a new one (the old one is invalidated).

**Step 6 — Note your three values.** You now have everything Trellis needs:

| Env var | Where it came from |
|---|---|
| `TRELLIS_SMS_PROVIDER` | always `"africas_talking"` in production |
| `TRELLIS_AT_USERNAME` | the app username from Step 3 (e.g., `trellisapp`) |
| `TRELLIS_AT_API_KEY` | the `atsk_...` key from Step 5 |

### Testing with a real Nigerian phone (PowerShell)

```powershell
# 1. CD to the sms directory FIRST. uvicorn looks for app.py in cwd.
cd C:\Users\patmekury\Downloads\Trellis\sms

# 2. Make sure the forecast file is present
copy ..\mvp\forecast_may_2026.json forecast.json

# 3. Set env vars in the SAME WINDOW where you'll run uvicorn.
$env:TRELLIS_SMS_PROVIDER = "africas_talking"
$env:TRELLIS_AT_USERNAME = "trellisapp"
$env:TRELLIS_AT_API_KEY = "atsk_<your-key-here>"

# 4. Install the AT SDK if not already installed
pip install africastalking

# 5. Start uvicorn with --reload so code changes auto-pick-up
uvicorn app:app --port 8000 --reload
```

Leave that window running. In a **second** PowerShell window:

```powershell
# 1. Verify the service is up. Use http://localhost:8000 — NEVER http://0.0.0.0:8000
#    (0.0.0.0 is a bind address, not a destination address; that URL won't connect)
Invoke-RestMethod "http://localhost:8000/"
# Should print provider: africas_talking and forecast_loaded: True

# 2. Build the enrollment body in THIS window. PowerShell variables are window-scoped.
$body = @{phone="+234XXXXXXXXXX"; lganame="Warri South"; wardname="Ekurede"; child_age_years=3; lang="en"} | ConvertTo-Json
echo $body  # must print a JSON object; if empty, re-run the assignment in this same window

# 3. Enroll the caregiver
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/enroll" -ContentType "application/json" -Body $body

# 4. Dispatch with only_changed=false to force a send
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dispatch?channel=respiratory&only_changed=false"

# 5. Confirm the message that was sent
Invoke-RestMethod "http://localhost:8000/audit?limit=5"
```

The phone should buzz within ~30 seconds of the dispatch call. The audit row's `message` field shows the exact SMS text that landed.

### Common traps — every one of these was hit during the 10 May 2026 live test

| Trap | Symptom | Fix |
|---|---|---|
| Wrong directory for uvicorn | `ERROR: Error loading ASGI app. Could not import module "app".` | `cd C:\...\Trellis\sms` *before* running uvicorn |
| `http://0.0.0.0:8000/` in a browser | "This site can't be reached" | Use `http://localhost:8000/` — 0.0.0.0 is the bind address, not a destination |
| PowerShell `curl` alias mangles JSON | `JSON decode error: Expecting property name enclosed in double quotes` | Use `Invoke-RestMethod` with `$body | ConvertTo-Json`, or `curl.exe` (the real binary) |
| `$body` is empty when /enroll is called | 422 "Field required" with `input: null` | Set `$body` in the same window where you call `Invoke-RestMethod`. Variables are window-scoped. |
| Schema mismatch on the SQLite database | `/dispatch` returns 500 with no useful error | An old `trellis_sms.db` from before the channel column was added breaks the dispatcher. Delete `sms/trellis_sms.db` and restart uvicorn to rebuild the schema fresh. |
| AT dispatch returns 500 silently | uvicorn shows `AttributeError: 'sqlite3.Row' object has no attribute 'get'` | Already fixed in `render_respiratory` call site (uses `e["child_age_years"]` not `e.get(...)`). Restart uvicorn to pick up the fix. |
| Outbox / Activity Statement empty after Success | None — AT dashboard lag | AT's dashboards refresh on a delay (~30-60 s). The wallet does deduct and the SMS does deliver — the dashboard view just takes time to catch up. |
| Sender ID shows as `AFRICASTKNG` | Custom alphanumeric IDs need NCC approval | Use the default for testing. For production deployment, register a custom ID (1-3 business days) via the AT dashboard. |

> **Cost-safety:** Always test with a single number first, never with a multi-ward roster, until you've verified the message text on your own phone. Default sender ID `AFRICASTKNG` works for all four major Nigerian carriers (MTN, Glo, Airtel, 9mobile) without registration.

## Audit log schema

Each send produces one row:

| Column | Type | Note |
|---|---|---|
| id | int | autoincrement |
| phone | str | E.164 |
| lganame, wardname | str | the ward at time of send |
| tier | str | the tier at time of send |
| message | str | the rendered message |
| provider | str | which provider was active |
| provider_response | json | full response (for debugging) |
| sent_at | timestamp | UTC |
| forecast_year, forecast_month | int | which forecast was used |

Query: `GET /audit?limit=200` returns recent rows.

## What this service does NOT do

- **No two-way SMS.** Inbound replies (e.g. caregiver asks "what does this mean?") are not handled. Add a webhook endpoint when needed.
- **No opt-in handshake.** The current `/enroll` endpoint trusts the caller. For production deployment, add a confirm-via-SMS double-opt-in.
- **No quiet hours.** Sends whenever `/dispatch` is hit. For production, gate on local time of day.
- **No personalisation by child age yet.** The `child_age_years` field is captured but not used in template rendering. A future template could differentiate U2 vs 2-5 vs 5+.

## Why this exists

Caregivers of children under five are the closest stakeholders to childhood pollution exposure. SMS is the lowest-common-denominator channel — works on every Nigerian phone, no smartphone or app needed, no data plan needed. The Trellis platform pushes the same 4-week-ahead tier forecast to the DHIS2 dashboard (decision-maker channel) and to caregivers as plain SMS (last-mile channel), so the same model output reaches both audiences in their native medium.
