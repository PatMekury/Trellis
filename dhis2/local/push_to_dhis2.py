"""Push Trellis forecasts to a local DHIS2 instance.

Pre-requisites (do these once, in order):
  1. docker compose up -d  (from this directory)
  2. wait ~3 minutes for DHIS2 to finish first-boot init
  3. open http://localhost:8080 ; log in as admin / district ; CHANGE THE PASSWORD
  4. update DHIS2_PASSWORD below to match
  5. python3 build_orgunits.py     # produces nigeria_orgunits.json + ward_uid_lookup.json
  6. python3 push_to_dhis2.py --setup    # creates data elements + data set + posts org units
  7. python3 push_to_dhis2.py            # pushes the forecast as data values

After step 7, query the data via /api/dataValueSets or visit Pivot Tables → Trellis 4-week forecast.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import requests

# Project root, resolved relative to this file (was a sandbox-absolute path).
from pathlib import Path as _Path
ROOT_DIR = _Path(__file__).resolve().parent.parent.parent

DHIS2_URL = "http://localhost:8080"
DHIS2_USER = "admin"
DHIS2_PASSWORD = "Justpath1*"  # set to match the password changed in the DHIS2 UI

HERE = Path(__file__).parent
ORGUNIT_JSON = HERE / "nigeria_orgunits.json"
WARD_UID_JSON = HERE / "ward_uid_lookup.json"
FORECAST_JSON = (ROOT_DIR / "mvp/forecast_may_2026.json")

# Optional: forecast files for additional periods (June-December 2026 climatology).
# These are written by model/forecast_horizon_2026.py.
FORECAST_GLOB_PATTERN = "forecast_2026_*.json"

# Stable UIDs for our data elements + one data set. These are deterministic so re-runs are idempotent.
DE_NO2 = "TrellisNO2A"
DE_RAIN = "TrellisRain"
DE_TEMP = "TrellisTemp"
DE_TIER = "TrellisTier"
DE_MALARIA = "TrellisMlr1"  # malaria-risk tier — added for the climate-sensitive disease forecasting layer
DS_FCST = "TrellisFcst"

session = requests.Session()
session.auth = (DHIS2_USER, DHIS2_PASSWORD)
session.headers.update({"Content-Type": "application/json"})


def check_alive():
    try:
        r = session.get(f"{DHIS2_URL}/api/me", timeout=10)
        if r.status_code == 401:
            sys.exit(f"401 Unauthorized — update DHIS2_PASSWORD in this script after changing the admin password in the DHIS2 UI.")
        r.raise_for_status()
        me = r.json()
        print(f"  authenticated as {me.get('name')}")
    except requests.exceptions.ConnectionError:
        sys.exit(f"Cannot reach {DHIS2_URL}. Is `docker compose up` running and DHIS2 finished booting?")


def post_orgunits():
    print("Posting organisation units...")
    payload = json.loads(ORGUNIT_JSON.read_text())
    r = session.post(
        f"{DHIS2_URL}/api/metadata?importMode=COMMIT&identifier=UID&mergeMode=REPLACE",
        json=payload,
    )
    print(f"  HTTP {r.status_code}")
    if r.status_code >= 300:
        print(r.text[:500])
    else:
        stats = r.json().get("stats", {})
        print(f"  imported: created={stats.get('created',0)} updated={stats.get('updated',0)} ignored={stats.get('ignored',0)}")


def post_data_elements():
    print("Posting Trellis data elements...")
    elements = [
        {"id": DE_NO2,  "name": "Trellis NO2 forecast",         "shortName": "NO2 fcst",
         "valueType": "NUMBER",   "domainType": "AGGREGATE", "aggregationType": "AVERAGE"},
        {"id": DE_RAIN, "name": "Trellis rainfall forecast",    "shortName": "Rain fcst",
         "valueType": "NUMBER",   "domainType": "AGGREGATE", "aggregationType": "AVERAGE"},
        {"id": DE_TEMP, "name": "Trellis temperature forecast", "shortName": "Temp fcst",
         "valueType": "NUMBER",   "domainType": "AGGREGATE", "aggregationType": "AVERAGE"},
        {"id": DE_TIER, "name": "Trellis alert tier",           "shortName": "Tier",
         "valueType": "TEXT",     "domainType": "AGGREGATE", "aggregationType": "NONE"},
        {"id": DE_MALARIA, "name": "Trellis malaria-risk tier", "shortName": "Malaria",
         "valueType": "TEXT",     "domainType": "AGGREGATE", "aggregationType": "NONE"},
    ]
    r = session.post(
        f"{DHIS2_URL}/api/metadata?importMode=COMMIT&identifier=UID&mergeMode=REPLACE",
        json={"dataElements": elements},
    )
    print(f"  HTTP {r.status_code}")
    if r.status_code >= 300:
        print(r.text[:500])


def post_data_set():
    """Create the Trellis data set covering the four data elements at monthly period type."""
    # We need to attach to all level-4 (ward) org units
    ward_uids = json.loads(WARD_UID_JSON.read_text())
    ward_uid_list = [{"id": v} for k, v in ward_uids.items() if k.startswith("Ward|")]

    print(f"Creating data set with {len(ward_uid_list)} ward org units...")
    ds = {
        "id": DS_FCST,
        "name": "Trellis 4-week forecast",
        "shortName": "Trellis fcst",
        "periodType": "Monthly",
        "dataSetElements": [
            {"dataElement": {"id": DE_NO2}},
            {"dataElement": {"id": DE_RAIN}},
            {"dataElement": {"id": DE_TEMP}},
            {"dataElement": {"id": DE_TIER}},
            {"dataElement": {"id": DE_MALARIA}},
        ],
        "organisationUnits": ward_uid_list,
        # Explicitly open the period window we publish into. 24 future periods
        # covers our 8-month rolling horizon with margin; expiryDays=0 means
        # historical writes (e.g. for backfilling Sentinel-5P observations) are
        # also accepted; openFuturePeriods=24 allows forecasts up to 2 years out.
        "openFuturePeriods": 24,
        "expiryDays": 0,
        "timelyDays": 0,
    }
    r = session.post(
        f"{DHIS2_URL}/api/metadata?importMode=COMMIT&identifier=UID&mergeMode=REPLACE",
        json={"dataSets": [ds]},
    )
    print(f"  HTTP {r.status_code}")
    if r.status_code >= 300:
        print(r.text[:500])


def push_forecast(extra_paths: list[Path] | None = None):
    print("Pushing Trellis forecast as dataValueSet...")
    # Always start with the canonical May 2026 forecast (model-based, validated horizon).
    forecast = json.loads(FORECAST_JSON.read_text())
    # Optionally append additional period files (climatology for Jun-Dec 2026).
    if extra_paths:
        for p in extra_paths:
            if p.exists():
                forecast.extend(json.loads(p.read_text()))
                print(f"  added {len(json.loads(p.read_text()))} rows from {p.name}")
    ward_uids = json.loads(WARD_UID_JSON.read_text())

    values = []
    matched = 0
    unmatched = []
    for f in forecast:
        key = f"Ward|{f['lganame']}|{f['wardname']}"
        ou = ward_uids.get(key)
        if not ou:
            unmatched.append(f"{f['lganame']}|{f['wardname']}")
            continue
        matched += 1
        period = f"{f['forecast_year']}{f['forecast_month']:02d}"
        if f.get("no2_forecast_umol_m2") is not None:
            values.append({"dataElement": DE_NO2, "period": period, "orgUnit": ou,
                           "value": str(round(f["no2_forecast_umol_m2"], 2))})
        if f.get("rainfall_forecast_mm") is not None:
            values.append({"dataElement": DE_RAIN, "period": period, "orgUnit": ou,
                           "value": str(round(f["rainfall_forecast_mm"], 1))})
        if f.get("t2m_forecast_c") is not None:
            values.append({"dataElement": DE_TEMP, "period": period, "orgUnit": ou,
                           "value": str(round(f["t2m_forecast_c"], 2))})
        values.append({"dataElement": DE_TIER, "period": period, "orgUnit": ou,
                       "value": f["tier"]})
        if f.get("malaria_risk_tier"):
            values.append({"dataElement": DE_MALARIA, "period": period, "orgUnit": ou,
                           "value": f["malaria_risk_tier"]})

    print(f"  matched {matched}/{len(forecast)} wards to org units, {len(unmatched)} unmatched")
    if unmatched[:5]:
        print(f"  example unmatched: {unmatched[:5]}")

    payload = {"dataValues": values}
    r = session.post(f"{DHIS2_URL}/api/dataValueSets", json=payload)
    print(f"  HTTP {r.status_code}")
    # DHIS2 wraps both success and partial-success in JSON; print structured info either way.
    try:
        body = r.json()
    except ValueError:
        print(r.text[:1000])
        return
    # Try the modern shape first ({"response":{"importSummaries":...}}), fall back to legacy.
    resp = body.get("response", body)
    ic = resp.get("importCount") or body.get("importCount") or {}
    if ic:
        print(f"  imported={ic.get('imported',0)} updated={ic.get('updated',0)} "
              f"ignored={ic.get('ignored',0)} deleted={ic.get('deleted',0)}")
    # Conflicts/rejections — DHIS2 returns these in different keys depending on path
    conflicts = resp.get("conflicts") or body.get("conflicts") or []
    if conflicts:
        print(f"  conflicts ({len(conflicts)}):")
        for c in conflicts[:10]:
            obj = c.get("object", "?")
            val = c.get("value", "?")
            print(f"    - object={obj} value={val}")
    rejected = resp.get("rejectedIndexes") or []
    if rejected:
        print(f"  rejectedIndexes (first 10): {rejected[:10]} (total={len(rejected)})")
    if r.status_code >= 300 and not (conflicts or rejected):
        # Nothing useful in structured fields; dump the body as a last resort
        print("  full response body:")
        print(json.dumps(body, indent=2)[:3000])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--setup", action="store_true",
                   help="One-time setup: post org units, data elements, data set")
    p.add_argument("--all-periods", action="store_true",
                   help="Push the canonical May 2026 forecast plus all forecast_2026_*.json files in this folder")
    p.add_argument("--forecast", type=str, default=None,
                   help="Explicit path to a single forecast file to push instead of (or in addition to) May 2026")
    args = p.parse_args()

    print(f"Talking to DHIS2 at {DHIS2_URL}")
    check_alive()

    if args.setup:
        post_orgunits()
        post_data_elements()
        post_data_set()
        print("Setup complete. Re-run without --setup to push the forecast.")
    else:
        extras: list[Path] = []
        if args.all_periods:
            for p2 in sorted(HERE.glob(FORECAST_GLOB_PATTERN)):
                extras.append(p2)
        if args.forecast:
            extras.append(Path(args.forecast).resolve())
        push_forecast(extra_paths=extras or None)


if __name__ == "__main__":
    main()