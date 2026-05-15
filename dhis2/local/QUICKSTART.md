# Trellis local DHIS2 + dashboard — quickstart

A complete, tested walkthrough for bringing up two services on your laptop:

- **DHIS2** on `http://localhost:8080` — the open-source health information system that holds Trellis forecasts as real DHIS2 data.
- **Trellis dashboard** on `http://localhost:8081` — the web view that reads the forecast back out of DHIS2 live.

This guide reflects what was actually debugged on a Windows + Docker Desktop + WSL2 machine. The order matters. Skipping a step will fail in a specific way described under "common errors" at the bottom.

## What's in this folder

| File | Role |
|---|---|
| `docker-compose.yml` | Brings up DHIS2 + Postgres on `localhost:8080` |
| `dhis.conf` | Database + encryption config for DHIS2; bind-mounted into the container |
| `build_orgunits.py` | Builds Nigeria → Delta → 25 LGAs → 268 wards as DHIS2 metadata |
| `nigeria_orgunits.json` | Pre-generated metadata (already built; ready to import) |
| `ward_uid_lookup.json` | Maps "LGA\|Ward" → DHIS2 UID; used by push_to_dhis2.py |
| `push_to_dhis2.py` | One-time setup + ongoing forecast push to your DHIS2 |
| `forecast_may_2026.json` | The 51-ward May 2026 forecast (static fallback) |
| `index.html` + assets | Trellis dashboard, set up to read live from DHIS2 |

## Prerequisites

- **Docker Desktop** for Windows (with WSL2 backend). Verify: `docker --version` and `docker compose version` both work in PowerShell.
- **Python 3** on your PATH. Verify: `python --version`.
- **A modern browser** for the DHIS2 UI and Trellis dashboard.
- A working internet connection on first run (Docker will pull `postgis/postgis:14-3.3` and `dhis2/core:2.41.4`, about 1.6 GB combined; once-only).

## Step 1 — Bring up DHIS2

```powershell
cd C:\Users\patmekury\Downloads\Trellis\dhis2\local
docker compose down -v   # only if a previous boot failed; clears any stale DB volume
docker compose up -d
```

Watch the boot. First-boot schema initialisation takes 3–5 minutes on Windows/WSL2:

```powershell
docker compose logs -f dhis2
```

The `dhis.conf` file is bind-mounted into the container at `/opt/dhis2/dhis.conf`. If you change Postgres credentials in `docker-compose.yml`, change them in `dhis.conf` too.

You'll see a lot of `column "..." already exists, skipping` warnings while Hibernate runs migrations. They are normal. Wait for the line:

```
Server startup in [N] milliseconds
```

Press Ctrl-C to stop following the log (the containers keep running).

Verify the API is reachable:

```powershell
curl.exe http://localhost:8080/api/system/info
```

You should get JSON containing `"version":"2.41.4"`. Open `http://localhost:8080` in a browser to see the login screen.

> **Heads-up.** In PowerShell, `curl` is an alias for `Invoke-WebRequest`, which has different syntax and does not accept `-u` for basic auth. Always type `curl.exe` to use the real curl binary that ships with Windows 10+.

## Step 2 — First login and password change

Default DHIS2 credentials (the literal username and password):

- Username: `admin`
- Password: `district`

Log in. Top right user menu → **Edit profile** → **Account** tab → set a new password. Save.

If the login page hangs at a spinner, the app context isn't ready yet. Wait 1–2 more minutes for full warmup, then refresh.

## Step 3 — Update the password in two places

The push script and the dashboard both authenticate to DHIS2 with hard-coded credentials. Update them after Step 2.

**`push_to_dhis2.py`**, line 28:

```python
DHIS2_PASSWORD = "your-new-password"
```

**`index.html`**, near line 287, inside the inline `<script>` block:

```javascript
const DHIS2_PASSWORD = "your-new-password";
```

> If you ever push this folder to a public git remote, redact those two lines first or move the password to an environment variable.

## Step 4 — Grant the admin user access to the Trellis hierarchy

DHIS2's admin user is bound to a default demo org-unit subtree. Trellis creates a separate Nigeria → Delta → LGA → Ward hierarchy. Until you grant the admin user access to that hierarchy, every data-value push will fail with `Organisation unit ... not in hierarchy of current user`.

In DHIS2: **Apps → Users** → find `admin` → **Edit** → in the **Organisation units** section, add **Nigeria** to all three sub-fields:

- Data capture organisation unit(s)
- Data output organisation unit(s) (or "Search organisation units")
- Maintenance organisation unit(s)

Save.

## Step 5 — Push Trellis metadata (org units, data elements, data set)

```powershell
cd C:\Users\patmekury\Downloads\Trellis\dhis2\local
pip install requests
python push_to_dhis2.py --setup
```

Expected output:

```
Talking to DHIS2 at http://localhost:8080
  authenticated as admin admin
Posting organisation units...
  HTTP 200
Posting Trellis data elements...
  HTTP 200
Creating data set with 268 ward org units...
  HTTP 200
Setup complete. Re-run without --setup to push the forecast.
```

> **Misleading stats — read this.** The script may print `imported: created=0 updated=0 ignored=0` for the org-unit block. This is **not a failure.** DHIS2 2.41 puts the real numbers in `typeReports[].stats`, but the script prints the top-level `stats` block, which is empty for metadata import. To verify the import actually worked, run this:
> ```powershell
> curl.exe -u "admin:your-new-password" "http://localhost:8080/api/organisationUnits.json?pageSize=5&fields=id,name,level"
> ```
> The response should report `"total":295`.

## Step 6 — Push the May 2026 forecast as data values

```powershell
python push_to_dhis2.py
```

Expected output:

```
Talking to DHIS2 at http://localhost:8080
  authenticated as admin admin
Pushing Trellis forecast as dataValueSet...
  matched 51/51 wards to org units, 0 unmatched
  HTTP 200
  imported=204 updated=0 ignored=0 deleted=0
```

204 = 51 wards × 4 data elements (NO₂ forecast, rainfall forecast, temperature forecast, alert tier).

If you instead see `HTTP 409` with `Organisation unit ... not in hierarchy of current user`, you skipped Step 4 — go back and grant admin access to Nigeria.

## Step 7 — Generate analytics tables (so Pivot Tables / Data Visualizer work)

DHIS2's Data Visualizer queries pre-aggregated analytics tables, not the raw `datavalue` table. On a fresh install with just-imported data, those tables are empty, so any pivot will return "Something went wrong. There's a problem with the generated analytics."

Build them once. Two equivalent paths:

**UI path (recommended):**

In DHIS2 → **Apps → Data Administration** → **Analytics tables** → click **Start export**. Wait for the right-side progress log to finish (under a minute for our small dataset).

**API path:**

```powershell
curl.exe -u "admin:your-new-password" -X POST "http://localhost:8080/api/resourceTables/analytics"
```

In production, this is run nightly via the DHIS2 scheduler.

## Step 8 — Allow CORS for the dashboard origin

The Trellis dashboard runs from `http://localhost:8081`. DHIS2's CORS allowlist by default does not include that origin, so browser fetches from the dashboard to DHIS2 will be blocked. Add the origin once.

**UI path:** **Apps → System Settings → Access** tab → **CORS allowlist** → add `http://localhost:8081` → Save.

**API path:**

```powershell
curl.exe -u "admin:your-new-password" -X POST "http://localhost:8080/api/systemSettings/keyCorsWhitelist" -H "Content-Type: text/plain" --data "http://localhost:8081"
```

## Step 9 — Verify in DHIS2's own UI

Open **Apps → Data Visualizer** → **New** → **Pivot Table**.

In the data picker, switch the category from "Data sets" to **"Data elements"**, search for `Trellis`, and select all four:

- Trellis NO₂ forecast
- Trellis rainfall forecast
- Trellis temperature forecast
- Trellis alert tier

Period: **May 2026** (`202605`).

Organisation units: pick **Delta State**; in the Level filter, choose **Ward** so the table flattens to leaf level.

Click **Update**. You should see 51 ward rows × 4 columns, with NO₂ values around 16–30, rainfall around 100–250, temperatures around 27–29, and tiers reading `likely`, `possible`, or `watch`.

> If you accidentally pick "Trellis 4-week forecast" from the **Data sets** category, you'll see four reporting-rate metrics (reporting rate, reporting rate on time, actual reports, expected reports) instead of the actual values. Those are auto-generated for every data set; ignore them, switch to Data elements.

## Step 10 — Bring up the Trellis dashboard on :8081

In a **second** PowerShell window (leave Docker running in the first):

```powershell
cd C:\Users\patmekury\Downloads\Trellis\dhis2\local
python -m http.server 8081
```

Open `http://localhost:8081/index.html` in the browser.

In the page header, top right, the data-source badge should read:

```
DHIS2 live · admin · model xgboost_v2_multiyear
```

If it reads "Static JSON (DHIS2 not reachable at http://localhost:8080)", open DevTools (F12) → Console → refresh, then check the error.

## Common errors and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Container restart loop with `File /opt/dhis2/dhis.conf cannot be read` | dhis.conf not mounted | Confirm `docker-compose.yml` has the bind mount line `./dhis.conf:/opt/dhis2/dhis.conf:ro`. Run `docker compose down -v` then `up -d` again. |
| Login page hangs at spinner | First-boot init still running | Wait 3–5 minutes total from `up -d`. Refresh. |
| `python push_to_dhis2.py --setup` returns 401 | Password constant didn't update | Re-edit `push_to_dhis2.py` line 28; confirm exact match with the password set in the DHIS2 UI. |
| `--setup` reports `created=0 updated=0 ignored=0` | Misleading output, not a real failure | Verify with `curl.exe ... /api/organisationUnits.json` — should report `"total":295`. |
| `python push_to_dhis2.py` returns 409 with `Organisation unit ... not in hierarchy of current user` | Step 4 skipped | Grant admin user access to Nigeria in Apps → Users. |
| Pivot Table shows "Something went wrong. There's a problem with the generated analytics" | Step 7 skipped | Run analytics-tables build via Data Administration or the API endpoint. |
| Dashboard badge reads "Static JSON" with CORS error in DevTools console | Step 8 skipped | Add `http://localhost:8081` to CORS allowlist. |
| Dashboard badge reads "Static JSON" with `409 Conflict` on `/api/dataValueSets?...&orgUnit=NigeriaRoot...` | Old placeholder UID in JS | `index.html` line 308 must use real Nigeria UID `l9SHnHVg86v`. |
| `curl: parameter cannot be processed because the parameter name 'u' is ambiguous` | PowerShell aliasing `curl` to `Invoke-WebRequest` | Use `curl.exe` (the real binary) instead of `curl`. |
| Port 8080 or 8081 already in use | Another service is bound there | Either stop that service, or change the port mapping in `docker-compose.yml` (8080→8090) and restart. |

## Tear-down

To stop the services without losing data:

```powershell
docker compose stop
```

To stop and **wipe the database** (e.g., to start fresh):

```powershell
docker compose down -v
```

The `-v` flag deletes the named volumes (`postgres-data`, `dhis2-files`). After a `down -v`, you must repeat Steps 4–8.

## What this gives you

- A self-hosted DHIS2 instance with Trellis-specific metadata: 295 organisation units, 4 data elements, 1 data set.
- 204 data values for May 2026 covering all 51 pilot wards.
- A working live link from the Trellis dashboard to the DHIS2 API.
- A reproducible local environment that any reviewer can stand up in 10–15 minutes following this guide.

## What this does NOT give you

- Real Delta State health-system case data — that requires a state-level data-sharing arrangement.
- Production hosting — localhost works for development; for production you would deploy DHIS2 to a real server with proper TLS, authentication, and backup policies.
- The full 7.5-year historical NO₂ time series in DHIS2 form — that's stored in CSVs in the project; the dashboard pulls it from `ward_timeseries.json` for the per-ward chart, not from DHIS2.
