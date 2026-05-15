# Trellis MCP server

Model Context Protocol server that exposes Trellis as a uniform tool interface. Any MCP-aware client (Claude Desktop, Cline, Continue.dev, your own MCP agent) can call Trellis tools the same way it calls any other tool. This is the third primary novelty lever from trellis.md: an open MCP architecture, not just four separate dashboards.

## Why an MCP server

The Trellis platform produces forecasts, exposure profiles, and decision-channel outputs. Without MCP, each consumer (a ministry analyst querying SQL, a clinician opening DHIS2, a researcher running a Jupyter notebook) talks to Trellis through a different surface. With MCP, all of them talk to Trellis through the same seven tools:

| Tool | What it answers |
|---|---|
| `trellis_forecast` | "What's the 4-week NO₂ forecast for Ekurede in Warri South?" |
| `trellis_ward_profile` | "Give me everything Trellis knows about ward Akpakpa." |
| `trellis_alert_list` | "Which wards are currently in alert?" |
| `trellis_priority_score` | "Recompute the sensor-siting score with child-population at 50% instead of 35%." |
| `trellis_send_advisory` | "Trigger a caregiver SMS for the wards in alert" — accepts `advisory_type=general\|malaria\|respiratory` for the SMS channel |
| `trellis_malaria_risk` | "What's the malaria-risk classification for Ekurede this month? Why?" — returns tier + EPIDEMIA-aligned rationale |
| `trellis_respiratory_alert` | "Is Ekurede in elevated paediatric respiratory exposure for under-5s? With toddler-asthma framing." |

A Claude Desktop user with the Trellis MCP installed can ask, "Which Delta wards have the highest forecast NO₂ for May 2026 and how many children under 5 do they hold?" and get an answer that calls `trellis_alert_list` + `trellis_ward_profile` automatically.

## Run it

### Standalone

```bash
cd mcp
pip install mcp pytest pytest-asyncio httpx
python3 server.py
```

The server speaks MCP over stdio. It expects the Trellis backend at `http://localhost:8001` (override with `TRELLIS_BACKEND_URL`). If the backend is not reachable, it falls back to reading the static forecast JSON from `mvp/forecast_may_2026.json`.

> **Don't forget `pytest-asyncio`.** Without it, three of the four tests in `tests/test_tools.py` fail with `async def functions are not natively supported`. The first test (`test_module_imports`) is synchronous so it passes regardless — that's how you know the package itself loads cleanly.

Run the test suite:

```bash
cd mcp
PYTHONPATH=. python -m pytest tests/ -v
```

Expected: 4 passed.

### With Claude Desktop — TESTED LIVE 15 May 2026

The config file lives at:

- Windows: `C:\Users\<your-username>\AppData\Roaming\Claude\claude_desktop_config.json` (`%APPDATA%\Claude\claude_desktop_config.json`)
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

#### Case 1 — the file doesn't exist yet

Create it. Open Notepad (or your editor):

```powershell
notepad $env:APPDATA\Claude\claude_desktop_config.json
```

Notepad will offer to create the file. Click Yes, paste this exactly, save (Ctrl-S):

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

#### Case 2 — the file already exists with other MCP servers

Don't replace it. Merge. Open the file, add a comma after your last entry's closing `}`, then paste **just the trellis block** (the inner part — not the surrounding `{ "mcpServers": { ... } }`):

```json
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
```

Place it inside the existing `"mcpServers": { ... }` object. The merged file looks like:

```json
{
  "mcpServers": {
    "some-existing-mcp": { ... existing ... },
    "trellis": {
      "command": "python",
      "args": [ "C:\\Users\\patmekury\\Downloads\\Trellis\\mcp\\server.py" ],
      "env": {
        "TRELLIS_BACKEND_URL": "http://localhost:8001",
        "TRELLIS_SMS_URL": "http://localhost:8000",
        "TRELLIS_FORECAST_PATH": "C:\\Users\\patmekury\\Downloads\\Trellis\\mvp\\forecast_may_2026.json"
      }
    }
  }
}
```

JSON rules: comma between sibling keys; **no trailing comma** after the last one. So between the existing entry and `"trellis"` → comma. After `"trellis"`'s closing `}` (if it's the last entry) → no comma.

#### Restart Claude Desktop

Right-click the Claude Desktop icon in the system tray (bottom-right of the Windows taskbar) → **Quit**. Re-launch from the Start menu. The MCP server starts when Claude Desktop launches; the seven Trellis tools appear in the tool list ~5 seconds later.

> **Closing the window is not enough.** Claude Desktop runs in the tray when you close the window. You must Quit from the tray to fully restart it and pick up the config change.

#### Smoke-test prompts

In a fresh Claude Desktop chat, ask any of these. Each should trigger a visible "Using tool: trellis_..." indicator before the answer.

> "What's the malaria risk for Ekurede in Warri South for May 2026, and why?"

Expected: Claude calls `trellis_malaria_risk` and returns the tier (likely / possible / watch) plus an EPIDEMIA-aligned rationale string like *"likely: rainfall 287mm in optimal breeding range; temperature 26.1C optimal for parasite development."*

> "Which Delta wards have elevated paediatric respiratory exposure for under-5s?"

Expected: Claude calls `trellis_alert_list` (or `trellis_respiratory_alert` per ward) and returns the wards above the NO₂ 75th-percentile threshold with the toddler-asthma framing note.

> "Recompute the sensor siting if I weight child population at 50% instead of 35%."

Expected: Claude calls `trellis_priority_score` with `weight_child=0.50` and returns the top 25 wards under the new ranking. Useful for stress-testing the siting analysis under different equity weights.

> **The backend doesn't have to be running** for `trellis_forecast`, `trellis_malaria_risk`, `trellis_respiratory_alert`, `trellis_alert_list`, and `trellis_priority_score` — they fall back to local JSON. For `trellis_send_advisory` to actually trigger SMS or surge, the SMS dispatcher (port 8000) and sensor backend (port 8001) must be up.

#### Common traps — every one hit during the 15 May 2026 live wire-up

| Symptom | Cause | Fix |
|---|---|---|
| Tools don't appear in Claude Desktop | Closed the window but didn't Quit from tray — old process still has cached config | Right-click tray icon → Quit → re-launch from Start menu |
| `python` command not found by Claude Desktop | Python on PATH for your shell but not for the GUI app | Use the full path in `command`: `"C:\\Python314\\python.exe"` instead of `"python"` |
| MCP server starts but no tools register | `mcp` package missing in the Python install Claude Desktop calls | `<that-python> -m pip install mcp httpx` |
| Claude Desktop says "Error loading MCP server" | JSON syntax error (usually trailing comma or unescaped backslash) | Validate at jsonlint.com. Paths in Windows need `\\` (double backslash), not single |
| Tool fires but returns "No forecast found" | `TRELLIS_FORECAST_PATH` points at a missing file | Confirm `mvp/forecast_may_2026.json` exists at the path in `env` |
| Tools register but Claude answers without using them | Claude judged the question didn't need a tool | Force it: "Use the trellis_malaria_risk tool to tell me..." or "Call trellis_alert_list to see..." |

### With Cline (VS Code MCP client)

Same config in Cline's `mcp.json`. Cline auto-detects when the server is reachable.

### Inspecting available tools

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 server.py
```

Returns a JSON-RPC response listing all five tools with their input schemas.

## Tool details

### `trellis_forecast`

```json
{ "lganame": "Warri South", "wardname": "Ekurede" }
```

Returns the forecast row for that ward — NO₂, rainfall, temperature, climatology, tier, model id.

### `trellis_ward_profile`

Same input as forecast. Returns full ward context: population, U5 count, facilities, flare BCM, NDVI, the last 12 months of NO₂ history, and the next-month forecast.

### `trellis_alert_list`

```json
{ "tier": "alert", "limit": 20 }
```

Filters by tier. `"alert"` = likely + possible. Sorted descending by forecast NO₂.

### `trellis_priority_score`

```json
{
  "weight_child": 0.50,
  "weight_no2": 0.20,
  "weight_coverage_gap": 0.20,
  "weight_flare": 0.10
}
```

Recomputes the per-ward priority score under custom weights and returns the top 25. Useful for asking "what changes if we double the equity weight?" — exactly the kind of question UNICEF reviewers will ask about the EOI siting analysis.

### `trellis_send_advisory`

```json
{ "channel": "sms", "advisory_type": "malaria", "lganame": "Warri South", "wardname": "Ekurede" }
```

Triggers an action on one of the four decision channels:

- `sms` → calls the Trellis SMS dispatcher's `/dispatch` endpoint. Optional `advisory_type` selects which template family: `general` (default), `malaria` (rainfall + temperature → mosquito breeding), or `respiratory` (toddler-asthma framing for high-NO₂ days).
- `dhis2` → returns instructions to refresh the DHIS2 dashboard
- `school` → returns instructions for the school PWA's data refresh
- `surge` → returns instructions for the surge UI

### `trellis_malaria_risk`

```json
{ "lganame": "Warri South", "wardname": "Ekurede" }
```

Returns the malaria-risk tier (likely / possible / watch) plus a one-line rationale derived from the EPIDEMIA-aligned threshold logic (rainfall 50-300 mm and temperature 22-30°C define the optimal range). Output explicitly notes "environmental-risk forecasting, not case-incidence forecasting" — the integration of DHIS2 surveillance case data is the eighth predictor and is currently an open question.

### `trellis_respiratory_alert`

```json
{ "lganame": "Warri South", "wardname": "Ekurede", "child_age_years": 2 }
```

Returns the paediatric respiratory exposure status (elevated vs within range) based on the ward's forecast NO₂ vs the pilot 75th-percentile threshold, plus a recommended caregiver action. If `child_age_years <= 3`, the action text is targeted at toddlers specifically (the most vulnerable lung-development window). Includes the framing note about toddler-asthma being implicated by NO₂ exposure in birth-cohort literature.

## Why this is novel

trellis.md identifies three primary novelty levers; the third is "open MCP server architecture." Most existing climate-health platforms expose dashboards, APIs, and dataset downloads. None of them expose themselves as a uniform agent-callable interface — meaning none of them are usable by an LLM-powered assistant without custom integration code.

The Trellis MCP server is what makes "an analyst chatting with their AI assistant about Niger Delta child health" work the same way as "the ministry's DHIS2 instance" — both flows hit the same backing data through the same tools, and the analyst gets the same answer the dashboard would show.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `TRELLIS_BACKEND_URL` | `http://localhost:8001` | Trellis sensor backend (forecast proxy, ward-current data) |
| `TRELLIS_SMS_URL` | `http://localhost:8000` | Trellis SMS dispatcher service |
| `TRELLIS_FORECAST_PATH` | (sandbox path) | Fallback forecast JSON if backend is unreachable |
| `TRELLIS_WARD_TS_PATH` | (sandbox path) | Ward time-series JSON for the profile tool |

## What this MCP does NOT expose

- **No write access to sensor readings.** Sensors push via the backend ingest endpoint with HMAC; agents do not.
- **No DHIS2 admin operations.** Reading live DHIS2 data is fine; creating org units, modifying data sets, etc. require a separate connector.
- **No firmware update calls.** Sensor OTA is out of scope.
- **No personal data lookups.** Caregiver phone numbers are stored only in the SMS dispatcher's SQLite; there is no MCP tool to read them.

## Open-source

This MCP server ships under MIT, like the rest of Trellis software. Forking and extending the tool set is encouraged. Please contribute new tools back to the upstream Trellis repository when they are general-purpose.
