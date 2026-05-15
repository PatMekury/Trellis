# Data card: health facilities and LGA layer

## Identity

- **Files:**
  - `data/health/delta_lgas.geojson` — 25 Delta LGA polygons (raw GRID3 pull)
  - `data/health/delta_lgas.gpkg` — same as GeoPackage
  - `data/health/delta_facilities.geojson` — 1,059 Delta health facility points (raw GRID3 pull)
  - `data/health/delta_health_facilities.gpkg` — same as GeoPackage
  - `data/health/delta_ward_facility_summary.csv` — per-ward facility counts by ownership and level
  - `data/health/preview/health_facilities_overview.png` — two-panel preview map
  - `data/health/build_health.py` — reproducible build script
  - GeoPackage layers in `trellis_delta_wards.gpkg`: `delta_lgas`, `delta_health_facilities`, `ward_facility_summary`
- **Format:** GeoJSON, OGC GeoPackage, CSV, PNG
- **CRS:** EPSG:4326
- **Created:** 9 May 2026

## Source

- **LGA boundaries:** GRID3 NGA — Operational LGA Boundaries (ArcGIS item `2bb616a49ee84f409427cc2143787113`). Authoritative admin-2 layer matching the ward (admin-3) layer's parent geography.
- **Health facilities:** GRID3 NGA — Health Facilities v2.0 (ArcGIS item `a0ed9627a8b240ff8b315a84575754a4`). Maintained registry of facility locations linked to the National Health Facility Registry (NHFR).
- **Publisher:** GRID3 Nigeria, in collaboration with the Federal Ministry of Health and the National Primary Health Care Development Agency (NPHCDA).
- **Access:** open via ArcGIS Hub Feature Service, anonymous query.
- **License:** Open data via GRID3 Data Hub (CC-BY equivalent).

## Coverage and signal

### Delta-wide totals

- 25 LGAs (matches the ward layer's parent count exactly)
- 1,059 health facilities

### Facility breakdown

| Dimension | Count |
|---|---|
| **Ownership: Public** | 518 |
| **Ownership: Private** | 251 |
| **Ownership: Unknown** | 290 |
| **Level: Primary (PHC)** | 869 |
| **Level: Secondary** | 180 |
| **Level: Tertiary** | 10 |

The 290 facilities flagged "Unknown" ownership are mostly facilities that exist in the NHFR but where the ownership field has not been reconciled. The Trellis platform should treat them as part of the visible service network for sensor-siting and SMS distribution purposes, not exclude them.

### Pilot LGA coverage

- Of the **51 pilot wards**, **48 have at least one facility** (94%).
- **3 pilot wards have zero health facilities:**
  - **Akugbene 2** (Bomadi LGA)
  - **Patani 2** (Patani LGA)
  - **Akpakpa** (Warri South-West LGA)
- 176 facilities total within the pilot ward polygons.

### Top wards by facility count (within pilot LGAs)

| LGA | Ward | Facilities | PHC | Public | Private |
|---|---|---|---|---|---|
| Warri South | Igbudu | 14 | 14 | 1 | 9 |
| Warri South | Okere | 13 | 10 | 5 | 6 |
| Warri South | Ekurede | 12 | 11 | 4 | 6 |
| Warri South | Esisi | 11 | 11 | 0 | 8 |
| Burutu | Ogulagha | 7 | 5 | 2 | 1 |

The Warri South pattern — high facility density, mixed public-private — matches expectations for a refinery and port city. Note the persistent appearance of Ekurede in the top wards: the same ward ranks high for both NO₂ exposure and facility density, which makes it a strong candidate for the first sensor-siting batch.

## Why these three zero-facility wards matter

Akugbene 2, Patani 2, and Akpakpa are exactly the wards where the Trellis early-warning channels (caregiver SMS, school advisory page, surge-planning to the nearest receiving facility) need to do the work that a co-located facility cannot. These are also the wards where any deployed sensor node will be high-leverage: a single sensor at a community site replaces the absent local clinical observation point.

## Schema

**Health facility points (`delta_health_facilities`)**

| Field | Description |
|---|---|
| `nhfr_uid`, `nhfr_facility_code` | National Health Facility Registry identifiers |
| `country`, `iso` | Nigeria, NGA |
| `statename`, `lganame`, `wardname` | Administrative location (NHFR-attributed; may differ from spatial join — see caveats) |
| `facility_name` | Facility name |
| `facility_name_source` | Provenance of the name string |
| `ownership` | Public / Private / Unknown |
| `ownership_type` | More granular subtype where available |
| `facility_level` | Primary / Secondary / Tertiary |
| `facility_level_option` | Subtype where available (Health Post, Health Centre, etc.) |
| `latitude`, `longitude` | Decimal degrees |
| `geocoordinates_source` | Provenance of the geocoordinates |
| `last_updated` | NHFR last-update timestamp |

**Per-ward summary (`ward_facility_summary`)** — one row per pilot ward

| Field | Description |
|---|---|
| `n_facilities`, `n_phc`, `n_secondary`, `n_tertiary` | Counts by level |
| `n_public`, `n_private` | Counts by ownership |

## Caveats

- **NHFR-attributed ward vs spatial-join ward.** GRID3 supplies a ward name on each facility record from the NHFR, but the registered ward sometimes disagrees with the polygon containing the facility's geocoordinates. 1,055 of 1,059 Delta facilities matched a ward polygon spatially; the four that didn't are likely on or just outside the LGA boundary. The build script preserves both versions and uses the spatial-join result for the per-ward count.
- **Geocoordinate quality.** GRID3 sources geocoordinates from multiple chains (NHFR, ward-validation campaigns, third-party). The `geocoordinates_source` field allows filtering to higher-confidence subsets if needed.
- **Ownership "Unknown" is a real category.** It is not safe to drop these from the count — they include functioning facilities that simply have unreconciled metadata.
- **NHFR is updated periodically.** The dataset will drift over time as facilities open, close, or are upgraded. Re-pulling annually is recommended.
- **No bed counts, no service mix.** This layer is location and metadata only. Service-level information (which facility delivers childhood immunisations, which has a maternity ward, which has functional cold-chain) requires a separate join to NPHCDA service-level datasets or DHIS2.

## Reproducibility

```bash
# LGAs
SVC_LGA="https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/NGA_LGA_Boundaries_2/FeatureServer/0"
curl -sL --get "$SVC_LGA/query" \
  --data-urlencode "where=statename='Delta'" \
  --data-urlencode "outFields=*" --data-urlencode "outSR=4326" --data-urlencode "f=geojson" \
  -o delta_lgas.geojson

# Health facilities
SVC_HF="https://services3.arcgis.com/BU6Aadhn6tbBEdyk/arcgis/rest/services/GRID3_NGA_health_facilities_v2_0/FeatureServer/0"
curl -sL --get "$SVC_HF/query" \
  --data-urlencode "where=state='Delta'" \
  --data-urlencode "outFields=*" --data-urlencode "outSR=4326" --data-urlencode "f=geojson" \
  -o delta_facilities.geojson

# Build derived layers
python3 build_health.py
```

## Next steps

1. **Cross-join to NPHCDA functional-PHC list.** The NHFR has more facilities than NPHCDA classifies as fully functional. The Trellis 10-PHC-sensor allocation should preference NPHCDA-listed functional PHCs.
2. **Service-mix layer.** Pull or derive which facilities run immunisation, antenatal, malaria-microscopy, and oxygen-capable services. Drives both DHIS2 predictor selection and surge-planning logic.
3. **Bed counts.** Hospital-level bed inventory comes from the State Ministry of Health, not GRID3. Add as a deliverable conditional on a future state-level data-sharing arrangement.
4. **Catchment polygons.** Compute realistic facility catchments (Voronoi or travel-time-weighted) for SMS targeting and DHIS2 catchment validation. Travel-time would benefit from joining to GRID3 transport-network if available.
