"""Trellis MCP server.

Exposes the Trellis platform as Model Context Protocol tools. Any MCP-aware client
(Claude Desktop, Cline, Continue.dev, custom agents) can call these tools to:

  - Get the current 4-week forecast for a ward
  - Pull a full ward profile (exposure, population, facilities)
  - List wards currently in alert
  - Recompute the sensor-siting score under custom weights
  - Send a Trellis advisory through any of the four decision channels

This is the third novelty lever from trellis.md: an open MCP architecture that
lets ministry analysts, researchers, and AI agents interact with the platform
through a uniform tool interface rather than four separate dashboards.

Run:
    pip install mcp
    python3 server.py

Or via stdio for client integration:
    python3 -m mcp.cli ./server.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:
    print("[trellis-mcp] mcp package not installed. Run: pip install mcp")
    raise SystemExit(1)

BACKEND = os.getenv("TRELLIS_BACKEND_URL", "http://localhost:8001")
SMS_API = os.getenv("TRELLIS_SMS_URL", "http://localhost:8000")
FORECAST_FALLBACK = Path(os.getenv(
    "TRELLIS_FORECAST_PATH",
    str(ROOT_DIR / "mvp/forecast_may_2026.json"),
))

server = Server("trellis")


# ============ HELPERS ============

async def get_forecast() -> list[dict]:
    """Fetch the 4-week forecast from the backend, fall back to local JSON."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BACKEND}/forecast")
            r.raise_for_status()
            return r.json()
    except Exception:
        if FORECAST_FALLBACK.exists():
            return json.loads(FORECAST_FALLBACK.read_text())
        return []


async def get_ward_profiles() -> dict[str, dict]:
    """Read the ward time-series JSON to expose ward static profiles."""
    p = Path(os.getenv("TRELLIS_WARD_TS_PATH",
        str(ROOT_DIR / "dhis2/ward_timeseries.json")))
    if p.exists():
        return json.loads(p.read_text())
    return {}


# ============ TOOLS ============

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="trellis_forecast",
            description=(
                "Get the next 4-week air-quality forecast for a Trellis pilot ward. "
                "Returns NO2 forecast, rainfall forecast, temperature forecast, and the "
                "alert tier (likely / possible / watch)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lganame": {"type": "string", "description": "LGA name, e.g. 'Warri South'"},
                    "wardname": {"type": "string", "description": "Ward name, e.g. 'Ekurede'"},
                },
                "required": ["lganame", "wardname"],
            },
        ),
        types.Tool(
            name="trellis_ward_profile",
            description=(
                "Get a complete profile for a Trellis pilot ward: population, children "
                "under 5, health-facility count, gas-flare exposure, current and historical "
                "NO2 readings."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lganame": {"type": "string"},
                    "wardname": {"type": "string"},
                },
                "required": ["lganame", "wardname"],
            },
        ),
        types.Tool(
            name="trellis_alert_list",
            description=(
                "List all pilot wards currently in alert (tier 'likely' or 'possible'). "
                "Useful for triage and surge planning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["likely", "possible", "watch", "alert"],
                        "description": "Filter to one tier. 'alert' = likely + possible.",
                    },
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        types.Tool(
            name="trellis_priority_score",
            description=(
                "Recompute the sensor-siting priority score for all 51 pilot wards under "
                "custom weights. The default weighting is child-population 35%, NO2 25%, "
                "coverage gap 25%, flares 15%. Pass alternative weights to see how the "
                "ward ranking shifts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "weight_child": {"type": "number", "default": 0.35},
                    "weight_no2": {"type": "number", "default": 0.25},
                    "weight_coverage_gap": {"type": "number", "default": 0.25},
                    "weight_flare": {"type": "number", "default": 0.15},
                },
            },
        ),
        types.Tool(
            name="trellis_send_advisory",
            description=(
                "Trigger a Trellis advisory through one of the four decision channels: "
                "DHIS2 dashboard refresh, school PWA push, caregiver SMS dispatch, or "
                "surge-planning supervisor brief. The SMS dispatch is rate-limited and "
                "idempotent; calling it twice will not double-send."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["dhis2", "school", "sms", "surge"],
                    },
                    "lganame": {"type": "string", "description": "Optional LGA filter"},
                    "wardname": {"type": "string", "description": "Optional ward filter"},
                    "advisory_type": {
                        "type": "string",
                        "enum": ["general", "malaria", "respiratory"],
                        "default": "general",
                        "description": (
                            "Which advisory layer to dispatch on the SMS channel: 'general' (env "
                            "alert tier), 'malaria' (rainfall/temperature-driven malaria risk), "
                            "or 'respiratory' (toddler-asthma framing for high-NO2 days). "
                            "Ignored for non-SMS channels."
                        ),
                    },
                },
                "required": ["channel"],
            },
        ),
        types.Tool(
            name="trellis_malaria_risk",
            description=(
                "Get the malaria-risk classification for a Trellis pilot ward. Returns the "
                "malaria-risk tier (likely / possible / watch) and a one-line rationale "
                "based on rainfall and temperature thresholds (EPIDEMIA-aligned methodology). "
                "This is environmental-risk forecasting, not case-incidence forecasting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lganame": {"type": "string"},
                    "wardname": {"type": "string"},
                },
                "required": ["lganame", "wardname"],
            },
        ),
        types.Tool(
            name="trellis_respiratory_alert",
            description=(
                "Get the paediatric respiratory exposure status for a Trellis pilot ward. "
                "Returns a flag for whether forecast NO2 places this ward in the top-25th "
                "percentile of paediatric exposure for the next 4 weeks (toddler-asthma "
                "framing). Includes the under-5 population estimate and recommended "
                "caregiver action. Consistent with the dashboard's 'Wards with elevated "
                "NO2 for under-5s' KPI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lganame": {"type": "string"},
                    "wardname": {"type": "string"},
                    "child_age_years": {
                        "type": "integer",
                        "description": "Optional: a specific child's age, used to target the advisory.",
                    },
                },
                "required": ["lganame", "wardname"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "trellis_forecast":
        return await tool_forecast(arguments)
    if name == "trellis_ward_profile":
        return await tool_ward_profile(arguments)
    if name == "trellis_alert_list":
        return await tool_alert_list(arguments)
    if name == "trellis_priority_score":
        return await tool_priority_score(arguments)
    if name == "trellis_send_advisory":
        return await tool_send_advisory(arguments)
    if name == "trellis_malaria_risk":
        return await tool_malaria_risk(arguments)
    if name == "trellis_respiratory_alert":
        return await tool_respiratory_alert(arguments)
    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def tool_forecast(args: dict) -> list[types.TextContent]:
    forecasts = await get_forecast()
    lga = args.get("lganame", "").strip()
    ward = args.get("wardname", "").strip()
    match = next((f for f in forecasts if f["lganame"] == lga and f["wardname"] == ward), None)
    if not match:
        return [types.TextContent(type="text",
            text=f"No forecast found for {lga} / {ward}. "
                 f"Available LGAs: {sorted(set(f['lganame'] for f in forecasts))}")]
    return [types.TextContent(type="text", text=json.dumps(match, indent=2))]


async def tool_ward_profile(args: dict) -> list[types.TextContent]:
    forecasts = await get_forecast()
    profiles = await get_ward_profiles()
    lga = args.get("lganame", "").strip()
    ward = args.get("wardname", "").strip()
    key = f"{lga}|{ward}"
    profile = profiles.get(key)
    forecast = next((f for f in forecasts if f["lganame"] == lga and f["wardname"] == ward), None)
    if not profile and not forecast:
        return [types.TextContent(type="text", text=f"No profile found for {lga} / {ward}.")]
    out = {
        "lganame": lga, "wardname": ward,
        "population": {
            "total": profile.get("pop_total") if profile else None,
            "under_5": profile.get("pop_under5") if profile else None,
        },
        "facilities": {
            "total": profile.get("fac_total") if profile else None,
            "phc": profile.get("fac_phc") if profile else None,
        },
        "exposure": {
            "flare_bcm_13yr": profile.get("flare_bcm") if profile else None,
            "ndvi_annual": profile.get("ndvi_annual") if profile else None,
        },
        "forecast_may_2026": forecast,
        "historical_no2_series": (profile.get("ts") if profile else [])[-12:],  # last 12 months
    }
    return [types.TextContent(type="text", text=json.dumps(out, indent=2))]


async def tool_alert_list(args: dict) -> list[types.TextContent]:
    forecasts = await get_forecast()
    tier = args.get("tier", "alert")
    limit = args.get("limit", 20)
    if tier == "alert":
        rows = [f for f in forecasts if f["tier"] != "watch"]
    else:
        rows = [f for f in forecasts if f["tier"] == tier]
    rows.sort(key=lambda r: r.get("no2_forecast_umol_m2") or 0, reverse=True)
    rows = rows[:limit]
    return [types.TextContent(type="text", text=json.dumps({
        "n_results": len(rows),
        "tier_filter": tier,
        "wards": rows,
    }, indent=2))]


async def tool_priority_score(args: dict) -> list[types.TextContent]:
    """Recompute the siting score across pilot wards under custom weights."""
    profiles = await get_ward_profiles()
    forecasts = await get_forecast()

    if not profiles:
        return [types.TextContent(type="text", text="ward profiles not loaded")]

    fc_by_key = {f"{f['lganame']}|{f['wardname']}": f for f in forecasts}

    rows = []
    for key, p in profiles.items():
        f = fc_by_key.get(key, {})
        rows.append({
            "lganame": p["lga"], "wardname": p["ward"],
            "pop_under5": p["pop_under5"],
            "no2": (f.get("no2_forecast_umol_m2") or 0),
            "flare_bcm": p["flare_bcm"],
            "fac_phc": p["fac_phc"],
        })

    def norm(values):
        if not values: return []
        mn, mx = min(values), max(values)
        if mx == mn: return [0] * len(values)
        return [(v - mn) / (mx - mn) for v in values]

    pops = norm([r["pop_under5"] for r in rows])
    no2s = norm([r["no2"] for r in rows])
    flares = norm([r["flare_bcm"] for r in rows])
    # Coverage gap: invert PHC density per child
    phc_density = [(r["fac_phc"] / max(r["pop_under5"], 1)) * 1000 for r in rows]
    gaps = [1 - x for x in norm(phc_density)]

    w_child = args.get("weight_child", 0.35)
    w_no2 = args.get("weight_no2", 0.25)
    w_gap = args.get("weight_coverage_gap", 0.25)
    w_flare = args.get("weight_flare", 0.15)
    total = w_child + w_no2 + w_gap + w_flare or 1
    w_child, w_no2, w_gap, w_flare = (x / total for x in (w_child, w_no2, w_gap, w_flare))

    for i, r in enumerate(rows):
        r["score"] = round(
            w_child * pops[i] + w_no2 * no2s[i] + w_flare * flares[i] + w_gap * gaps[i], 3
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    out = {
        "weights_used": {
            "child": w_child, "no2": w_no2,
            "coverage_gap": w_gap, "flare": w_flare,
        },
        "n_wards": len(rows),
        "top_25": rows[:25],
    }
    return [types.TextContent(type="text", text=json.dumps(out, indent=2))]


async def tool_send_advisory(args: dict) -> list[types.TextContent]:
    channel = args.get("channel")
    if channel == "sms":
        advisory_type = args.get("advisory_type", "general")
        if advisory_type not in ("general", "malaria", "respiratory"):
            return [types.TextContent(type="text",
                text=f"Invalid advisory_type '{advisory_type}'. Use general | malaria | respiratory.")]
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{SMS_API}/dispatch", params={"channel": advisory_type})
                r.raise_for_status()
                return [types.TextContent(type="text",
                    text=f"SMS dispatch result ({advisory_type} channel): {r.json()}")]
        except Exception as e:
            return [types.TextContent(type="text",
                text=f"SMS dispatch failed (is the SMS service running at {SMS_API}?): {e}")]
    if channel == "dhis2":
        return [types.TextContent(type="text",
            text="DHIS2 dashboard refreshes automatically when the forecast file is updated by "
                 "the Trellis pipeline. To force a manual refresh, replace mvp/forecast_may_2026.json "
                 "with the latest output from model/forecast_may2026.py and run "
                 "dhis2/local/push_to_dhis2.py if running against your local DHIS2.")]
    if channel == "school":
        return [types.TextContent(type="text",
            text="School PWA fetches the forecast on every page open. The service worker caches "
                 "for offline use. To push an update, ensure the forecast.json on the server has been refreshed.")]
    if channel == "surge":
        return [types.TextContent(type="text",
            text="Surge UI is a polling client. To push an update, refresh the page or the underlying forecast.json.")]
    return [types.TextContent(type="text", text=f"Unknown channel: {channel}")]


async def tool_malaria_risk(args: dict) -> list[types.TextContent]:
    """Return the malaria-risk classification for a given ward."""
    # Local import to keep module load fast even when malaria_risk isn't on path
    import sys
    sys.path.insert(0, str(ROOT_DIR / "model"))
    try:
        from malaria_risk import classify_malaria_risk, explain_classification
    except ImportError:
        return [types.TextContent(type="text",
            text="malaria_risk module not found. Expected at model/malaria_risk.py.")]

    forecasts = await get_forecast()
    lga = args.get("lganame", "").strip()
    ward = args.get("wardname", "").strip()
    f = next((x for x in forecasts if x["lganame"] == lga and x["wardname"] == ward), None)
    if not f:
        return [types.TextContent(type="text",
            text=f"No forecast found for {lga} / {ward}.")]

    rain = f.get("rainfall_forecast_mm")
    temp = f.get("t2m_forecast_c")
    # If the forecast already has malaria_risk_tier embedded, use that as the
    # canonical answer; otherwise compute on the fly.
    cached = f.get("malaria_risk_tier")
    tier = cached or classify_malaria_risk(rain, temp)
    rationale = explain_classification(rain, temp)

    out = {
        "lganame": lga,
        "wardname": ward,
        "forecast_year": f.get("forecast_year"),
        "forecast_month": f.get("forecast_month"),
        "malaria_risk_tier": tier,
        "rainfall_mm": rain,
        "temperature_c": temp,
        "rationale": rationale,
        "framing": (
            "Environmental-risk forecasting (rainfall + temperature thresholds, "
            "EPIDEMIA-aligned). Not case-incidence forecasting. To interpret as "
            "case incidence, integrate DHIS2 surveillance data."
        ),
    }
    return [types.TextContent(type="text", text=json.dumps(out, indent=2))]


async def tool_respiratory_alert(args: dict) -> list[types.TextContent]:
    """Return the paediatric respiratory exposure status for a given ward."""
    forecasts = await get_forecast()
    lga = args.get("lganame", "").strip()
    ward = args.get("wardname", "").strip()
    age = args.get("child_age_years")

    f = next((x for x in forecasts if x["lganame"] == lga and x["wardname"] == ward), None)
    if not f:
        return [types.TextContent(type="text",
            text=f"No forecast found for {lga} / {ward}.")]

    no2 = f.get("no2_forecast_umol_m2") or 0
    # Domain-wide 75th percentile flag (consistent with dashboard KPI)
    all_no2 = sorted([x.get("no2_forecast_umol_m2") or 0 for x in forecasts])
    p75 = all_no2[int(len(all_no2) * 0.75)] if all_no2 else 0
    elevated = no2 >= p75

    profiles = await get_ward_profiles()
    pop_under5 = profiles.get(f"{lga}|{ward}", {}).get("pop_under5", 0)

    if elevated:
        action_en = (
            "Caregivers of under-5s: keep children indoors during midday (11am-3pm). "
            "If your child has diagnosed asthma, follow their action plan; have "
            "reliever inhaler ready. Visit PHC immediately if wheeze or fast "
            "breathing does not settle."
        )
        if age is not None and age <= 3:
            action_en = (
                f"Toddler ({age} y): the under-5 lung is most vulnerable in this age band. "
                + action_en
            )
    else:
        action_en = "Air healthy for under-5s currently. Maintain routine."

    out = {
        "lganame": lga,
        "wardname": ward,
        "forecast_year": f.get("forecast_year"),
        "forecast_month": f.get("forecast_month"),
        "no2_forecast_umol_m2": no2,
        "pilot_p75_threshold_umol_m2": p75,
        "elevated_for_under5s": elevated,
        "ward_under5_population": pop_under5,
        "alert_tier": f.get("tier"),
        "child_age_years": age,
        "recommended_action": action_en,
        "framing": (
            "Toddler-asthma framing: NO2 exposure is implicated in early-childhood "
            "asthma onset (multiple birth-cohort studies; Brunst et al.; Khreis et al. "
            "meta-analysis). The school-channel sensors measure exactly the perimeter "
            "air toddlers breathe during the school day."
        ),
    }
    return [types.TextContent(type="text", text=json.dumps(out, indent=2))]


# ============ ENTRY ============

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())