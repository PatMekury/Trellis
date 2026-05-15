# Running a private DHIS2 instance for Trellis

A one-page setup guide for spinning up your own DHIS2 server in Docker, importing Nigeria's organisation unit hierarchy, and connecting Trellis to it. About 30 minutes from cold start to a working URL.

This is the path to having full control of a DHIS2 instance: you own the credentials, the data, and the infrastructure. The connector code you write against this instance is identical to the code you'll point at any other DHIS2 instance later. Only the URL and credentials change.

## Prerequisites

- A machine (laptop or VPS) with at least 4 GB RAM and 5 GB free disk
- Docker and Docker Compose installed
- Either Linux, macOS, or Windows with WSL2

That's it. No DHIS2 account, no partnership, no signup.

## Step 1: Bring up DHIS2

Create a working directory and a `docker-compose.yml`:

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgis/postgis:14-3.3
    environment:
      POSTGRES_USER: dhis
      POSTGRES_PASSWORD: dhis
      POSTGRES_DB: dhis
    volumes:
      - postgres-data:/var/lib/postgresql/data

  dhis2:
    image: dhis2/core:2.41.4
    depends_on:
      - postgres
    environment:
      WAIT_FOR_DB_CONTAINER: postgres:5432 -t 0
      DHIS2_DATABASE_URL: jdbc:postgresql://postgres:5432/dhis
      DHIS2_DATABASE_USERNAME: dhis
      DHIS2_DATABASE_PASSWORD: dhis
    ports:
      - "8080:8080"
    volumes:
      - dhis2-data:/opt/dhis2

volumes:
  postgres-data:
  dhis2-data:
```

Start it:

```bash
docker compose up -d
```

Wait two to three minutes for first-time database initialisation. Then open `http://localhost:8080` in a browser. Default credentials:

- Username: `admin`
- Password: `district`

**Change that password immediately** under `User profile → Account → Edit profile`.

## Step 2: Import Nigeria organisation units

DHIS2 ships with a starter database from the WHO COVID-19 metadata pack. To replace it with Nigeria's organisation unit hierarchy, you have three options:

### Option A — Import from the GRID3 admin boundaries you already have

You already have GRID3 v2.0 ward and LGA polygons in `data/trellis_delta_wards.gpkg`. Convert them to a DHIS2 metadata import:

```python
# scripts/build_dhis2_orgunits.py
import geopandas as gpd
import json
import uuid

def gen_uid(seed):
    """DHIS2 uids are 11 chars, alphanumeric, starts with letter."""
    h = abs(hash(seed))
    return "Trellis" + str(h)[:4]

# Load wards from your existing GeoPackage
delta = gpd.read_file("data/trellis_delta_wards.gpkg", layer="delta_wards")
lgas = gpd.read_file("data/trellis_delta_wards.gpkg", layer="delta_lgas")

org_units = []

# Country root
org_units.append({
    "id": "NigeriaRoot", "name": "Nigeria", "shortName": "Nigeria",
    "level": 1, "openingDate": "1900-01-01",
})

# State (Delta)
org_units.append({
    "id": "DeltaState1", "name": "Delta State", "shortName": "Delta",
    "level": 2, "parent": {"id": "NigeriaRoot"},
    "openingDate": "1991-08-27",
})

# LGAs (admin-2)
for _, r in lgas.iterrows():
    uid = gen_uid("lga_" + r["lganame"])
    org_units.append({
        "id": uid, "name": r["lganame"], "shortName": r["lganame"][:50],
        "level": 3, "parent": {"id": "DeltaState1"},
        "coordinates": json.dumps(list(r.geometry.exterior.coords)) if r.geometry.geom_type == "Polygon" else None,
        "openingDate": "1991-08-27",
    })

# Wards (admin-3)
for _, r in delta.iterrows():
    uid = gen_uid("ward_" + r["lganame"] + "_" + r["wardname"])
    parent_uid = gen_uid("lga_" + r["lganame"])
    org_units.append({
        "id": uid, "name": r["wardname"], "shortName": r["wardname"][:50],
        "level": 4, "parent": {"id": parent_uid},
        "openingDate": "1991-08-27",
    })

with open("nigeria_orgunits.json", "w") as f:
    json.dump({"organisationUnits": org_units}, f, indent=2)
print(f"Wrote {len(org_units)} organisation units")
```

Then POST to your local DHIS2:

```bash
curl -u admin:YOURNEWPASSWORD -X POST \
  -H "Content-Type: application/json" \
  --data-binary @nigeria_orgunits.json \
  "http://localhost:8080/api/metadata?importMode=COMMIT&identifier=UID"
```

### Option B — Use a community-maintained Nigeria metadata pack

The DHIS2 community sometimes shares country metadata packs on the [DHIS2 Community of Practice](https://community.dhis2.org). Search there for "Nigeria org unit hierarchy" before building your own. Saves you the GRID3-to-DHIS2 conversion work.

### Option C — Start with the empty DHIS2 starter and build org units interactively

If you only need a handful of test wards, the DHIS2 web UI under `Maintenance → Organisation Unit` lets you click-add the hierarchy yourself. Slower but no scripts.

## Step 3: Define the data elements that Trellis pushes

In DHIS2 web UI under `Maintenance → Data Element`, create these data elements:

| Name | Short name | Value type | Aggregation type |
|---|---|---|---|
| Trellis NO₂ forecast | NO2_FCST | Number | AVERAGE |
| Trellis rainfall forecast | RAIN_FCST | Number | AVERAGE |
| Trellis temperature forecast | TEMP_FCST | Number | AVERAGE |
| Trellis alert tier | TIER | Text | NONE |

Then create a Data Set called "Trellis 4-week forecast" with these four data elements, monthly period type, assigned to the ward (level-4) organisation units.

## Step 4: Push Trellis forecasts to your DHIS2

Once org units and data elements are defined, the connector posts forecasts as `dataValueSets`:

```python
# scripts/push_to_dhis2.py
import requests, json

DHIS2_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "YOURNEWPASSWORD"

forecast = json.load(open("mvp/forecast_may_2026.json"))

# Map ward names to DHIS2 org-unit UIDs
# (build this lookup from the import you did in Step 2)
ward_uids = json.load(open("dhis2/ward_uid_lookup.json"))

# Map data element names to UIDs
# (look up via /api/dataElements?fields=id,name)
de_no2 = "NO2_FCST_UID"
de_rain = "RAIN_FCST_UID"
de_temp = "TEMP_FCST_UID"
de_tier = "TIER_UID"

values = []
for f in forecast:
    ou_uid = ward_uids.get(f"{f['lganame']}|{f['wardname']}")
    if not ou_uid: continue
    period = f"{f['forecast_year']}{f['forecast_month']:02d}"  # 202605
    if f["no2_forecast_umol_m2"] is not None:
        values.append({"dataElement": de_no2, "period": period, "orgUnit": ou_uid, "value": f["no2_forecast_umol_m2"]})
    if f["rainfall_forecast_mm"] is not None:
        values.append({"dataElement": de_rain, "period": period, "orgUnit": ou_uid, "value": f["rainfall_forecast_mm"]})
    if f["t2m_forecast_c"] is not None:
        values.append({"dataElement": de_temp, "period": period, "orgUnit": ou_uid, "value": f["t2m_forecast_c"]})
    values.append({"dataElement": de_tier, "period": period, "orgUnit": ou_uid, "value": f["tier"]})

payload = {"dataValues": values}
r = requests.post(
    f"{DHIS2_URL}/api/dataValueSets",
    json=payload,
    auth=(USERNAME, PASSWORD),
)
print(r.status_code, r.text[:300])
```

## Step 5: Point the Trellis dashboard at your DHIS2

Modify `dhis2/index.html` to fetch from the DHIS2 Web API instead of static JSON. The replacement reads:

```javascript
// Replace the static fetches in dhis2/index.html with these.
const DHIS2_BASE = "http://localhost:8080";
const auth = "Basic " + btoa("admin:YOURNEWPASSWORD");

async function loadForecastFromDhis2() {
    // Read the latest period's data values
    const r = await fetch(
        `${DHIS2_BASE}/api/analytics?dimension=dx:NO2_FCST_UID;RAIN_FCST_UID;TEMP_FCST_UID;TIER_UID&dimension=ou:LEVEL-4;OU_GROUP-DELTA&dimension=pe:LAST_MONTH&displayProperty=NAME&outputIdScheme=UID`,
        { headers: { Authorization: auth } }
    );
    const data = await r.json();
    return data;  // adapt this to your dashboard's expected shape
}
```

## What you have at the end

- A DHIS2 instance running locally at `localhost:8080` that you fully own
- Nigeria's admin hierarchy populated as DHIS2 organisation units
- Trellis forecasts pushed to DHIS2 as `dataValueSets`, queryable via `/api/analytics`
- A dashboard that talks to a real DHIS2 server end-to-end
- The exact same connector code that will work against any other DHIS2 instance you point at later — just change the URL

## What this does NOT give you

- **Real Delta health-system data.** The DHIS2 instance you stand up is *your* instance with *your* org-unit hierarchy. The historical childhood malaria, ARI, and immunisation data is owned by the relevant state ministry of health, accessible only via a future data-sharing arrangement to be identified and negotiated.
- **Production hosting.** Localhost works for development; production needs a real server (your own infrastructure, AWS, Hetzner, etc.).
- **DHIS2 expertise.** The DHIS2 platform is large. Read the [DHIS2 Implementation Guide](https://docs.dhis2.org/en/implement/maintenance-and-use/orientation-to-the-implementation-guide.html) when you're ready to go beyond the basics.

## Reference URLs

- DHIS2 official Docker image: `https://hub.docker.com/r/dhis2/core`
- DHIS2 documentation: `https://docs.dhis2.org`
- DHIS2 Web API reference: `https://docs.dhis2.org/en/develop/using-the-api/dhis-core-version-master/introduction.html`
- DHIS2 Community of Practice: `https://community.dhis2.org`
- DHIS2 metadata patterns / starter kits: `https://docs.dhis2.org/en/topics/metadata`

## Cost and effort honest summary

- **Today (you, 30 min):** stand up Docker DHIS2, get to login screen.
- **Today (you, 1 hour):** import Nigeria org units, define data elements.
- **Today (me, 1 hour):** rewrite the dashboard to call the local DHIS2 instead of static JSON.
- **Total time to "Trellis dashboard talks to a real DHIS2 instance":** ~2.5 hours.
- **Cost:** $0. Your laptop or any cheap VPS.

Once this is running locally, integration with any state ministry of health DHIS2 is a single configuration change away — only the URL and credentials differ.
