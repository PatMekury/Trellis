# Data card: trellis_delta_wards.gpkg

## Identity

- **File:** `data/trellis_delta_wards.gpkg`
- **Format:** OGC GeoPackage (SQLite-backed); two layers
- **CRS:** EPSG:4326 (WGS 84, geographic)
- **Created:** 9 May 2026 (v1.0 baseline) → revised 9 May 2026 to GRID3 v2.0
- **Created by:** Trellis project, Cowork session
- **Purpose:** Canonical admin-3 boundary file for Trellis. Every ward-level join — EO pixel aggregation, DHIS2 facility catchment, sensor placement, forecast issuance — uses these polygons.

## Layers

| Layer | Features | Coverage |
|---|---|---|
| `delta_wards` | 268 | All 25 LGAs of Delta State |
| `pilot_wards` | 51 | Five candidate pilot LGAs: Warri South, Warri South-West, Burutu, Bomadi, Patani |

Pilot ward counts by LGA: Burutu 11, Warri South 10, Warri South-West 10, Bomadi 10, Patani 10.

All 268 polygons in `delta_wards` are non-null and topologically valid. All 51 polygons in `pilot_wards` are non-null and topologically valid.

## Source

- **Dataset:** GRID3 NGA — Operational Wards v2.0 (April 2026 release)
- **Publisher:** GRID3 Nigeria (National Population Commission, National Bureau of Statistics, Office of the Surveyor General of the Federation, Columbia University CIESIN)
- **Item ID (ArcGIS):** 9ab61cff803a497986bf2716898c6902
- **Feature service:** https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/main_GRID3_NGA_operational_wards_v2_0/FeatureServer/0
- **States covered by v2.0:** Adamawa, Bauchi, Bayelsa, Borno, **Delta**, Gombe, Jigawa, Kano, Katsina, Kwara, Niger, Ogun, Osun, Oyo, Yobe (15 of 36 + FCT)
- **Date stamp on Delta features:** 2026-03-31
- **Source attribution per feature:** mostly `CIESIN`
- **License:** Open data via GRID3 Data Hub (CC-BY equivalent; verify exact terms before redistribution)

## Schema

Stable Trellis-side fields (renamed from v2.0 originals for cross-version continuity):

| Trellis field | v2.0 source field | Notes |
|---|---|---|
| `statename` | `state` | "Delta" |
| `lganame` | `lga` | LGA name |
| `wardname` | `ward` | Ward name |
| `statecode` | `statecode` | Two-letter code |
| `country`, `iso3` | unchanged | "Nigeria", "NGA" |
| `lga_alt_names`, `ward_alt_names` | unchanged | Alt-name strings where present |
| `multipart_count` | unchanged | Number of polygon parts |
| `source` | unchanged | Per-feature data lineage |
| `date` | unchanged | Feature timestamp |
| `area_sqkm` | unchanged | Area in km² |

ArcGIS-internal fields removed: `OBJECTID`, `Shape__Area`, `Shape__Length`.

## v1.0 → v2.0 changes for Delta State

- **Ward count:** 267 → 268 (one additional ward in Ika South LGA)
- **Burutu / Egodor:** v1.0 had a null polygon (status="Invalid", source="INEC"). v2.0 supplies a complete MultiPolygon, 171 km², dated 2026-03-31, sourced from CIESIN. **This was the gap that motivated the v2.0 swap.**
- **Bomadi spelling:** three wards have minor name spelling/punctuation changes — `Kolafiogbene / Ekametagbene` → `Ekaametagbene/Kalafio`; `Ogbeinma / Okoloba` → `Ogbeinma/Okoloba`; `Ogo / Eze` → `Ogo/Eze`. Same wards, same polygons; the v2.0 spelling should be treated as canonical.
- **Validity:** v1.0 had 1 invalid + 1 null geometry in Delta. v2.0 has zero invalid and zero null.
- **Geometry fidelity:** v2.0 polygons are higher-resolution (file size ~13 MB vs 0.7 MB for v1.0).

The other four pilot LGAs (Warri South, Warri South-West, Burutu, Patani) have identical ward names between v1.0 and v2.0.

## Bounding boxes (EPSG:4326)

- Delta State: 5.0072 W, 4.9750 S, 6.7991 E, 6.5341 N
- Pilot LGAs: 5.1571 W, 5.0118 S, 6.2930 E, 5.8299 N

The pilot bbox is what downstream EO pulls (Sentinel-2, Sentinel-5P, VIIRS, CHIRPS) should be parameterised against.

## How it was built

```bash
# Pull Delta wards from the v2.0 Feature Service
SVC="https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/main_GRID3_NGA_operational_wards_v2_0/FeatureServer/0"
curl -sL --get "$SVC/query" \
  --data-urlencode "where=state='Delta'" \
  --data-urlencode "outFields=*" \
  --data-urlencode "outSR=4326" \
  --data-urlencode "f=geojson" \
  -o delta_wards_v2.geojson

# Rename schema to Trellis canonical, write GeoPackage
python3 build_wards.py
```

The build script is at `data/build_wards.py`.

## Reproducibility note

GRID3 v2.0 is a versioned release; pulling the same item ID returns the same snapshot. If GRID3 publishes v2.1 or v3.0 in the future, the build script can be re-pointed by changing the item ID and the schema-rename block re-validated.
