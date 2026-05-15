# Trellis primary care surge planning UI

Single-page web app for primary health centre supervisors. Reads the same Trellis 4-week forecast as the DHIS2 dashboard but presents it in a workflow built around weekly staffing, stock, and triage decisions rather than ministry-level analytics.

## What the supervisor sees

- **Top KPI strip** — highest-priority ward, count of wards in alert, total exposed children U5, fraction of wards with at least one PHC
- **Ranked ward list** — wards sorted by a `priority = NO₂ × children-U5 / 1000` score with a visual bar. Tier-coloured pill, suggested action per tier, click-to-drill-down
- **Filters** — LGA dropdown, tier filter (all / likely / possible / alert / watch), sortable columns
- **Per-ward detail** — forecast, climatology, facility count, suggested action paragraph, free-text supervisor note (saved to browser localStorage)
- **Export** — weekly roster CSV per filter selection
- **Morning brief** — print-optimised one-page-per-LGA summary, ready to be printed and walked into the morning meeting

## Run it

The UI is a single HTML file. Open it any way:

```bash
cd surge
python3 -m http.server 8082
# then visit http://localhost:8082
```

Or just `open index.html` (most browsers will block fetch from `file://`; use the http server for development).

## Priority score

`priority = (forecast NO₂ in μmol/m²) × (children under 5 in ward) / 1000`

This is the "exposed-child-units" measure — ward-month NO₂ dose multiplied by the population it would affect. It collapses two separate dimensions into a single sortable number so the supervisor can see at a glance which wards are both high-exposure and high-population.

A ward with high NO₂ but few children (Pessu, 4,862 U5) ranks below a ward with moderate NO₂ but many children (Ekurede, 12,247 U5). This is correct for staffing decisions.

## Suggested actions per tier

The "Action" column and the per-ward detail use these rules:

- **Likely:** pre-position oxygen and nebuliser stock at the lead PHC. Brief community health workers on respiratory triage. Send caregiver SMS now.
- **Possible:** maintain standard staffing. Confirm inhaler stock at PHCs. Monitor weekly. Defer caregiver SMS until tier escalates.
- **Watch:** routine schedule. No additional action.

These are placeholders that should be calibrated against actual childhood respiratory case data once that becomes accessible to the project. The action language is in `index.html` inside `selectWard()` and the morning-brief renderer; modify there to match local protocols.

## Supervisor notes

Each ward has a free-text note field. Notes are saved to browser localStorage with the key `trellis_surge_note__<LGA>|<Ward>`. They persist across sessions in the same browser but **do not sync between devices**. For multi-supervisor or multi-device deployment, replace the localStorage block with a backend API call.

## What this UI does NOT do

- **No staffing roster generation.** The CSV export is a ranked ward list; building a real shift roster from it requires the supervisor's knowledge of staff availability.
- **No notifications or alerts.** The supervisor needs to open the page; there is no push or email layer.
- **No multi-week forecast.** Only the next-month forecast is shown. Trellis's pipeline supports rolling 4-week-ahead forecasts; the UI extension is straightforward but not yet built.
- **No outcome feedback.** Once a ward gets staffed up or stock moved, there is no way to mark it "actioned" that propagates back to the dashboard. localStorage notes are a placeholder for that.

## Why this is a separate channel from the DHIS2 dashboard

The DHIS2 dashboard (in `Trellis/dhis2/`) is built for ministry-level analytics, multi-period comparison, and DHIS2 integration. The surge UI here is built for a single PHC supervisor making this-week decisions about staff and stock. They share the same data layer but their workflows, time horizons, and information density differ enough that one UI for both would compromise both.

## How it composes with the rest of the platform

| Channel | Audience | Use case |
|---|---|---|
| DHIS2 dashboard | State ministry of health analyst | Multi-period analytics, evaluation, trend monitoring |
| **Surge UI (this)** | **PHC supervisor** | **Weekly staffing and stock decisions** |
| School advisory PWA | Primary school administrator | Daily morning brief for school activities |
| Caregiver SMS | Caregiver of a child U5 | Tier-changed alert in plain text |

All four read the same `forecast.json` from the Trellis pipeline. Each presents that forecast in the format and register their audience needs.
