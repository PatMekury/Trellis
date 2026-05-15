# Trellis — run everything (one-pass guide)

A single guide for standing up the full Trellis stack on a Windows + Docker Desktop + WSL2 machine, plus every correction we discovered along the way. Designed so a UNICEF reviewer (or you, after a break) can reproduce the platform from scratch in about an hour.

The stack has four runnable subsystems plus three browser-served dashboards. Run the four subsystems in this order:

1. **DHIS2 self-host** (port 8080) — open-source DHIS2 + Postgres in Docker
2. **Sensor backend** (port 8001) — FastAPI + Postgres+PostGIS in Docker, ingests HMAC-signed sensor readings
3. **SMS dispatcher** (port 8000) — FastAPI service for caregiver SMS, mock or real provider
4. **MCP server** — stdio MCP server, integrates with Claude Desktop or any MCP-aware client

And these dashboards (file-server on different ports):

- **Live DHIS2 dashboard** (port 8081) — `dhis2/local/index.html`, reads forecasts live from DHIS2
- **MVP dashboard** (port 8082 or 8081 if not running the live one) — `mvp/index.html`, full nine-tab platform demo
- **Surge planning UI** (port 8083) — `surge/index.html`, PHC supervisor view with per-disease tabs

## Prerequisites

- Docker Desktop for Windows with WSL2 backend
- Python 3.10+ on PATH
- A modern browser (Chrome / Edge / Firefox)
- ~3 GB free disk for Docker images
- Ports 5432 (DHIS2 Postgres), 8000 (SMS), 8001 (sensor backend), 8080 (DHIS2 web), 8081 (live dashboard), 8082+ (other dashboards) free

## PowerShell vs CMD

Most commands below assume PowerShell. If you're in CMD, two adjustments:

| PowerShell | CMD |
|---|---|
| `$env:VAR = "value"` | `set VAR=value` (no quotes, no spaces around `=`) |
| `curl.exe` (always use the `.exe`) | `curl` (no aliasing trap in CMD) |
| `Invoke-RestMethod` | not available; use `curl` |

The single most common Windows-curl trap: in PowerShell, **`curl` is an alias for `Invoke-WebRequest`**, which has different syntax and rejects `-u` for basic auth. **Always type `curl.exe`** when you mean the real curl binary.

---

## 1. DHIS2 self-host

Detailed walkthrough lives at `dhis2/local/QUICKSTART.md`. The condensed version:

```powershell
cd C:\Users\patmekury\Downloads\Trellis\dhis2\local
docker compose down -v        # only if a previous boot failed
docker compose up -d
docker compose logs -f dhis2   # wait for "Server startup in [N] milliseconds"
```

Open `http://localhost:8080`, log in `admin` / `district`, change the password (User profile → Account). Update the new password in two places:

- `dhis2/local/push_to_dhis2.py` line 28 — `DHIS2_PASSWORD = "your-new-password"`
- `dhis2/local/index.html` line ~287 — `const DHIS2_PASSWORD = "your-new-password";`

**Three corrections we hit and fixed today** (without these, push_to_dhis2.py fails):

1. **Admin user needs org-unit access to Nigeria.** The seeded admin user is bound to a default demo subtree, not our Nigeria → Delta hierarchy. Open Apps → Users → admin → Edit. In the **Organisation units** section, add **Nigeria** to all three sub-fields (data capture, data output, maintenance). Save. *Without this, `/dataValueSets` POST returns "Organisation unit not in hierarchy of current user" and rejects every value.*
2. **Data set must accept future periods.** The push script's data set definition includes `openFuturePeriods: 24` and `expiryDays: 0`. *Without this, periods past the current month are rejected with "Period does not conform to open periods".*
3. **CORS allowlist must include the dashboard origin.** Apps → System Settings → Access → CORS allowlist → add `http://localhost:8081`. Save. *Without this, the dashboard at :8081 cannot fetch from DHIS2 at :8080.*

Then push metadata + values:

```powershell
pip install requests
cd C:\Users\patmekury\Downloads\Trellis\dhis2\local
python push_to_dhis2.py --setup              # 295 org units + 5 data elements + 1 data set
python push_to_dhis2.py --all-periods         # 8 monthly periods × 51 wards × 5 elements = 2,040 values
```

> **Misleading-stats trap:** The `--setup` org-units block prints `created=0 updated=0 ignored=0`. **This is not a failure.** DHIS2 2.41 puts real numbers in `typeReports[].stats`, but the script reads the top-level `stats` block (which is empty for metadata import). To verify, run:
> ```powershell
> curl.exe -u "admin:your-password" "http://localhost:8080/api/organisationUnits.json?pageSize=5&fields=id,name,level"
> ```
> The response should include `"total":295`.

After pushing, rebuild the analytics tables so Pivot Tables can see the data:

```powershell
curl.exe -u "admin:your-password" -X POST "http://localhost:8080/api/resourceTables/analytics"
```

Verify in the DHIS2 UI: Apps → Data Visualizer → Pivot Table. Pick the five data elements (NO₂, rainfall, temperature, alert tier, malaria-risk tier). Period 202605 to 202612 (eight months). Org units: Delta State + Level=Ward. Update.

---

## 2. Sensor backend (Docker)

```powershell
cd C:\Users\patmekury\Downloads\Trellis\backend
docker compose up -d --build      # ~2 min for first build
docker compose ps                  # both containers should be Up + healthy
```

Verify the API is up:

```powershell
Invoke-RestMethod "http://localhost:8001/"
```

> **PostGIS ward attribution must be loaded.** Sensor enrollments and readings get attributed to wards via PostGIS `ST_Contains` against the `ward_polygons` table. That table is created empty by the schema. **You must call `/admin/load-wards` once** to populate it from `data/trellis_delta_wards.gpkg`:
> ```powershell
> Invoke-RestMethod -Method Post -Uri "http://localhost:8001/admin/load-wards"
> ```
> Expected: `{"loaded": 51}`. Without this, `lganame` and `wardname` are `null` on every sensor enrollment, and `/wards/{lga}/{ward}/current` returns "no readings in the last hour" even after readings have been ingested.

Enroll a sensor and run the simulator:

```powershell
$body = @{sensor_id="TR-06"; channel="PHC"; latitude=5.5347; longitude=5.7639; secret="dev-secret-tr06"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8001/sensors" -ContentType "application/json" -Body $body

python simulate_sensor.py        # full smoke test: enroll → send 5 → query → ward current
```

> **HMAC secret mismatch trap:** The simulator hardcodes `SENSOR_SECRET = "dev-secret-tr06"` (line 23). If you enrolled the sensor with a different secret, the simulator's HMAC signing will fail verification on `/ingest`. Either re-enroll with `dev-secret-tr06` (the simulator's `--enroll` does this), or edit the constant in the script.

> **Don't run uvicorn on the host.** The backend is designed to run fully inside Docker — Postgres has no host-side port mapping. Running `uvicorn app:app` from PowerShell can't reach the DB. Use `docker compose up` only.

The unit test suite covers HMAC verification (positive and negative paths), Pydantic validation, and the schema. Run from the repository root:

```powershell
cd C:\Users\patmekury\Downloads\Trellis\backend
pip install pytest pytest-asyncio httpx
$env:PYTHONPATH = "."
python -m pytest tests/ -v
```

Expected: 10 tests pass, including `test_hmac_rejects_wrong_signature` (the regression test for the original audit's deal-breaker).

---

## 3. SMS dispatcher

```powershell
cd C:\Users\patmekury\Downloads\Trellis\sms
pip install -r requirements.txt
copy ..\mvp\forecast_may_2026.json forecast.json
uvicorn app:app --port 8000
```

The service starts on `http://localhost:8000`. The default provider is `mock` — it logs to the console instead of sending real SMS. To dispatch:

```powershell
# Enroll an English-speaking caregiver in Ekurede with a 3-year-old
$body = @{phone="+2348011111111"; lganame="Warri South"; wardname="Ekurede"; child_age_years=3; lang="en"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/enroll" -ContentType "application/json" -Body $body

# Three independent channels — each tracks dispatch state separately
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dispatch?channel=general"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dispatch?channel=malaria"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dispatch?channel=respiratory"

# See the rendered messages in the audit log
Invoke-RestMethod "http://localhost:8000/audit?limit=20"
```

The `general` channel uses the existing alert-tier text. The `malaria` channel uses `render_malaria` (EPIDEMIA-aligned, ITN + RDT messaging). The `respiratory` channel uses `render_respiratory` (toddler-asthma framing — references inhaler, midday-indoor advisory, the under-5 lung development concern).

### Switching from mock to real SMS provider — TESTED LIVE 10 May 2026

For the full step-by-step Africa's Talking account + Team + App + API-key walkthrough see `sms/README.md`. The short version below assumes you already have the three values: AT username, AT API key, and a topped-up wallet (₦100+ is plenty).

**In the uvicorn window — order matters: cd, then env vars, then uvicorn:**

```powershell
cd C:\Users\patmekury\Downloads\Trellis\sms
copy ..\mvp\forecast_may_2026.json forecast.json

# Africa's Talking (Nigerian carrier delivery)
$env:TRELLIS_SMS_PROVIDER = "africas_talking"
$env:TRELLIS_AT_USERNAME = "trellisapp"               # the username of your AT App, NOT "sandbox"
$env:TRELLIS_AT_API_KEY = "atsk_<your-key-here>"      # from email after Settings → API Key → Request

pip install africastalking
uvicorn app:app --port 8000 --reload
```

Or **Twilio** for international fallback (Nigerian numbers cost ~$0.05 vs AT's ~$0.003):
```powershell
$env:TRELLIS_SMS_PROVIDER = "twilio"
$env:TRELLIS_TWILIO_SID = "ACxxxxxxxx"
$env:TRELLIS_TWILIO_TOKEN = "your-token"
$env:TRELLIS_TWILIO_FROM = "+12025551234"
pip install twilio
uvicorn app:app --port 8000 --reload
```

In a **second** PowerShell window, verify the service is up, then enroll and dispatch:

```powershell
# Use http://localhost:8000 — NEVER http://0.0.0.0:8000 (that's a bind address, won't connect)
Invoke-RestMethod "http://localhost:8000/"
# Expected: provider: africas_talking, forecast_loaded: True

# $body must be set in THIS window — PowerShell variables don't cross windows
$body = @{phone="+234XXXXXXXXXX"; lganame="Warri South"; wardname="Ekurede"; child_age_years=3; lang="en"} | ConvertTo-Json
echo $body  # confirm not empty

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/enroll" -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/dispatch?channel=respiratory&only_changed=false"
Invoke-RestMethod "http://localhost:8000/audit?limit=5"
```

**If you've used Trellis SMS in mock mode previously:** delete `sms/trellis_sms.db` before this run. The schema was extended on 10 May 2026 to add a `channel` column to `last_tier`, and SQLite's `CREATE TABLE IF NOT EXISTS` doesn't migrate existing tables. Without deleting the old DB, `/dispatch` returns 500 because the `channel` column doesn't exist.

The `only_changed=false` flag forces a send even if no tier transition has occurred since the last dispatch.

> **Cost note:** Africa's Talking sandbox is free for the first ~1,000 messages but only delivers to numbers explicitly verified in the AT dashboard. Twilio has a small per-message fee. Always test with a single number first, never with the full 51-ward roster, until you've verified the message text.

---

## 4. MCP server

```powershell
cd C:\Users\patmekury\Downloads\Trellis\mcp
pip install mcp pytest pytest-asyncio httpx
$env:PYTHONPATH = "."
python -m pytest tests/ -v
```

Expected: 4 tests pass.

> **Don't forget `pytest-asyncio`.** Without it, three of the four tests fail with "async def functions are not natively supported". Symptom: 1 pass + 3 fail with that exact error string.

To run the server in stdio mode (for an MCP client to consume):

```powershell
python server.py
```

The server waits silently for an MCP client. Press Ctrl-C to stop. The server registers seven tools:

- `trellis_forecast` — get 4-week forecast for a ward
- `trellis_ward_profile` — full per-ward profile (population, facilities, exposure)
- `trellis_alert_list` — list wards in alert
- `trellis_priority_score` — recompute siting score under custom weights
- `trellis_send_advisory` — trigger a decision channel (DHIS2 / school / SMS / surge), with `advisory_type` selector for SMS (general / malaria / respiratory)
- `trellis_malaria_risk` — malaria-risk classification for a ward, with EPIDEMIA-aligned rationale
- `trellis_respiratory_alert` — paediatric respiratory exposure status, with toddler-asthma framing

### Wiring MCP into Claude Desktop — TESTED LIVE 15 May 2026

Full step-by-step walkthrough is in `mcp/README.md`. Short version below.

Edit Claude Desktop's config file:

```
%APPDATA%\Claude\claude_desktop_config.json     # Windows
~/Library/Application Support/Claude/claude_desktop_config.json     # macOS
```

**If the file doesn't exist yet,** create it with this content:

```json
{
  "mcpServers": {
    "trellis": {
      "command": "python",
      "args": [
        "C:\\Users\\patmekury\\Downloads\\Trellis\\mcp\\server.py"
      ],
      "env": {
        "TRELLIS_BACKEND_URL": "http://localhost:8001",
        "TRELLIS_SMS_URL": "http://localhost:8000",
        "TRELLIS_FORECAST_PATH": "C:\\Users\\patmekury\\Downloads\\Trellis\\mvp\\forecast_may_2026.json"
      }
    }
  }
}
```

**If the file already has other MCP servers,** merge the `"trellis": { ... }` block into the existing `mcpServers` object. Put a comma after the previous entry's closing `}` and add the trellis block before `mcpServers`'s closing `}`. JSON's no-trailing-comma rule applies — the last entry has no comma after it.

> **Quit Claude Desktop from the system tray to restart.** Closing the window leaves the process running in the tray with the old config cached. Right-click the tray icon → Quit → re-launch from Start menu. New config picks up ~5 seconds after launch.

In a new Claude Desktop chat:

> "What's the malaria risk for Ekurede in Warri South for May 2026, and why?"

Expected: Claude shows a "Using tool: trellis_malaria_risk" indicator before answering, then returns the tier (likely / possible / watch) and an EPIDEMIA-aligned rationale like *"likely: rainfall 287mm in optimal breeding range; temperature 26.1C optimal for parasite development."*

> **Backend doesn't have to be running** for `trellis_malaria_risk`, `trellis_forecast`, `trellis_alert_list`, `trellis_respiratory_alert`, and `trellis_priority_score` — they fall back to local JSON. For `trellis_send_advisory` (SMS / DHIS2 / school / surge channels), the corresponding service must be up.

---

## 5. Dashboards

Each dashboard is just static files served via `python -m http.server`. Each on a separate port.

### Live DHIS2 dashboard (the linkage view)

```powershell
cd C:\Users\patmekury\Downloads\Trellis\dhis2\local
python -m http.server 8081
```

Open `http://localhost:8081/index.html`. Header badge should read **"DHIS2 live · admin · model xgboost_v2_multiyear"** (not "Static JSON"). If it says Static JSON, check that you added `http://localhost:8081` to the DHIS2 CORS allowlist (see DHIS2 section above).

This dashboard has the linkage panel (pollution → environment → disease causal chain), the multi-axis time-series chart, the feature-importance panel, and the autocomplete ward search.

### MVP dashboard (full nine-tab platform demo)

```powershell
cd C:\Users\patmekury\Downloads\Trellis\mvp
python -m http.server 8082
```

Open `http://localhost:8082/index.html`. Has the full nine tabs: overview, sensor map, decision channels, school PWA preview, etc.

### Surge planning UI (per-disease tabs)

```powershell
cd C:\Users\patmekury\Downloads\Trellis\surge
python -m http.server 8083
```

Open `http://localhost:8083/index.html`. Three tabs at top: **General environmental alert**, **Malaria risk**, **Paediatric respiratory**. Each shows a different ward ranking and disease-specific PHC actions.

### School advisory PWA

```powershell
cd C:\Users\patmekury\Downloads\Trellis\pwa-school
python -m http.server 8084
```

Mobile-first. Add to home screen on a phone for offline-capable behaviour.

---

## Common gotchas summary (the "every vital correction we made" cheat sheet)

| Symptom | Cause | Fix |
|---|---|---|
| Container restart loop with `dhis.conf cannot be read` | dhis.conf not bind-mounted | Confirm `docker-compose.yml` has `./dhis.conf:/opt/dhis2/dhis.conf:ro` |
| `python push_to_dhis2.py` returns 409 "Organisation unit not in hierarchy of current user" | admin user not granted access to Nigeria subtree | DHIS2 UI: Apps → Users → admin → Edit → add Nigeria to all three org-unit fields |
| `dataValueSet` push 409 "Period does not conform" | data set's openFuturePeriods is too low | Set to 24 in push_to_dhis2.py, re-run --setup |
| Pivot Table empty / "Something went wrong with the analytics" | analytics tables not built since last data import | POST `/api/resourceTables/analytics`, wait ~60 s |
| Pivot shows "reporting rate" / "reporting rate on time" instead of values | wrong data category selected | Switch from Data sets to Data elements; pick the four Trellis DEs |
| Dashboard shows "Static JSON" badge with CORS error | DHIS2 CORS allowlist doesn't include the dashboard origin | Add `http://localhost:8081` to System Settings → Access → CORS |
| Dashboard shows "Static JSON" with 409 on `&orgUnit=NigeriaRoot` | placeholder UID never replaced in JS | `index.html` line 308 must use `l9SHnHVg86v` |
| `curl: parameter cannot be processed because the parameter name 'u' is ambiguous` | PowerShell aliases `curl` to `Invoke-WebRequest` | Use `curl.exe` for the real binary |
| Sensor enrollment shows `lganame=null`, `wardname=null` | `ward_polygons` table empty | POST `/admin/load-wards` once |
| Sensor `/ingest` returns 401 with valid-looking body | HMAC secret mismatch — wrong secret signed the body | Either re-enroll with the secret in the simulator, or edit `SENSOR_SECRET` in simulate_sensor.py |
| MCP tests fail with "async def functions are not natively supported" | `pytest-asyncio` not installed | `pip install pytest-asyncio` |
| `host:5433` connection refused for backend | Postgres only on Docker internal network | Run backend in Docker (`docker compose up`); don't run uvicorn on host |
| SMS audit log shows only some channels | dispatcher ran but `only_changed=true` skipped repeats | Re-run with `?only_changed=false` to force send |
| `uvicorn` errors with `Could not import module "app"` | Running from `C:\WINDOWS\system32` or other folder | `cd C:\Users\patmekury\Downloads\Trellis\sms` before running uvicorn |
| `http://0.0.0.0:8000/` "site can't be reached" in a browser | `0.0.0.0` is a bind address, not a destination | Use `http://localhost:8000/` from your machine |
| SMS enroll returns 422 `Field required` with `input: null` | `$body` variable not set in the same PowerShell window | Re-assign `$body = ... | ConvertTo-Json` in the same window as `Invoke-RestMethod` |
| SMS `/dispatch` returns 500 with no obvious cause | Stale `trellis_sms.db` from before the `channel` column was added | Delete `sms/trellis_sms.db`, restart uvicorn, re-enroll, re-dispatch |
| SMS Outbox / Activity Statement empty after a Success response | AT dashboard refresh lag | Wait 30-60 s, refresh. The wallet *does* deduct and the SMS *does* deliver — the dashboard view just trails |
| AT API key page asks for password and shows nothing | The key is delivered out-of-band via email | After clicking Request, check `patrickobumselu@gmail.com` for a one-time link |
| AT account home page shows only Sandbox + "New Team" | Production wallet lives inside a Team's App, not the account root | Click **New Team** → name it → enter the team → **Create App** → that App has the wallet and API key |

---

## Live-test record

The session-by-session record of what's been validated end-to-end.

### 10 May 2026 (sprint day five)

- DHIS2 self-host: 2,040 values × 8 monthly periods (May–Dec 2026) × 5 data elements pushed and queryable via Pivot Tables. Hybrid forecast horizon: model for May, climatology for Jun–Dec.
- Sensor backend: TR-06 enrolled, HMAC-signed readings ingested + queryable. Calibration math verified.
- MCP server: 4/4 unit tests pass with `pytest-asyncio` installed.
- SMS dispatcher: mock provider exercised against the new general / malaria / respiratory channel split.
- Dashboards: linkage panel, multi-axis time-series, feature-importance panel, autocomplete search added to the live DHIS2 dashboard.

### 15 May 2026

- **SMS — Nigerian carrier delivery:** Africa's Talking production app `trellisapp` provisioned, ₦100 wallet topped, API key generated. `python -c` direct test delivered to `+2347062033758` on MTN. Then full `/dispatch?channel=respiratory&only_changed=false` flow delivered the toddler-asthma respiratory SMS through the Trellis service. Wallet deducted ₦4 per message. Audit log records `provider: africas_talking`.
- **SMS — US international carrier delivery:** Same AT account, US E.164 destination. AT routed the message internationally; payload landed on the US phone. Confirms Trellis SMS dispatcher can reach numbers outside Nigeria when needed.
- **MCP — Claude Desktop integration:** `claude_desktop_config.json` populated with the Trellis MCP block (merge-not-replace pattern documented). Claude Desktop restarted via system-tray Quit. The seven Trellis tools (`trellis_forecast`, `trellis_ward_profile`, `trellis_alert_list`, `trellis_priority_score`, `trellis_send_advisory`, `trellis_malaria_risk`, `trellis_respiratory_alert`) are now reachable from any MCP-aware client, including the very session you're reading this in.

### Bugs found and fixed during the 15 May 2026 live tests

| Bug | Effect | Fix |
|---|---|---|
| `sqlite3.Row` doesn't have `.get()` — used in `render_respiratory` call site | `/dispatch?channel=respiratory` returned 500 | Changed `e.get("child_age_years")` to `e["child_age_years"]` in `sms/app.py`. Restart uvicorn with `--reload` and the change picks up automatically. |
| `last_tier` table missing `channel` column for users upgrading from a pre-channel-split DB | First `/dispatch` after the upgrade returned 500 | Delete `sms/trellis_sms.db` so init_db rebuilds the schema fresh. Documented in the common-traps tables. |
| `http://0.0.0.0:8000/` is unreachable from a browser | Confusion when verifying uvicorn is up | Documented: use `http://localhost:8000/` from your own machine; `0.0.0.0` is the bind address only. |

### Outstanding tests (planned but not yet run)

- `trellis_send_advisory` triggered through a Claude Desktop prompt — actually firing the SMS channel from an agent conversation rather than from PowerShell. Demonstrates the agent-to-channel loop closing.
- DHIS2 + sensor backend running simultaneously while a forecast push triggers an SMS dispatch — end-to-end "data lands in DHIS2 and caregivers get notified" sequence on the same machine.

After both, the platform has been independently validated across **all four decision channels** (DHIS2 dashboard, school advisory, caregiver SMS, surge planning) plus the **MCP integration layer** — the third novelty lever from `trellis.md` is no longer hypothetical.

---

## Files modified or added today (10 May 2026)

- `model/malaria_risk.py` (new) — EPIDEMIA-aligned malaria-risk classifier
- `model/forecast_horizon_2026.py` (new) — rolling 8-month forecast generator
- `mvp/forecast_may_2026.json`, `forecast_dec_2025.json`, `forecast_2026_06.json` … `forecast_2026_12.json` — forecast files with malaria_risk_tier + climatology for Jun-Dec
- `dhis2/local/forecast_may_2026.json`, `forecast_2026_*.json` — same, mirrored
- `dhis2/local/push_to_dhis2.py` — adds TrellisMlr1 data element, --all-periods flag, openFuturePeriods=24
- `dhis2/local/index.html` — linkage panel, overlaid time-series, feature-importance panel, autocomplete search
- `mvp/index.html` — KPI tiles updated for malaria + paediatric resp.
- `surge/index.html` — three disease tabs (General / Malaria / Paediatric respiratory)
- `sms/app.py` — `render_malaria` + `render_respiratory` template families, channel-partitioned dispatch state
- `mcp/server.py` — `trellis_malaria_risk` + `trellis_respiratory_alert` tools
- `trellis_md_drafts/section_06_malaria_methodology.md` (new) — methodology with EPIDEMIA lineage
- `dhis2/local/QUICKSTART.md` — full regenerated quickstart with all gotchas
- `dhis2/local/feature_importance.json` (new) — top-8 features per target from trained model
- This `RUN_EVERYTHING.md` (new) — single-pass guide

For session-by-session change history, see `day1_wrap.md` through `day5_wrap.md` plus the `AUDIT_REPORT.md` / `AUDIT_CLOSURE.md` pair.
