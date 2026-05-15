# Development archive

Process artefacts kept for reference. **Nothing here is required to run Trellis** — everything in this folder can be deleted if you want a cleaner repository.

## Contents

### `sprint-log/`
Per-day wrap-up notes from the five-day platform sprint:

- `day1_wrap.md` — initial multi-year EO ingest, predictor table, baseline forecast
- `day2_wrap.md` — production DHIS2 app, school PWA, Sentinel-1 SAR
- `day3_wrap.md` — DHIS2 self-host stack, SMS dispatcher, surge UI
- `day4_wrap.md` — sensor backend with PostGIS + HMAC, firmware skeleton
- `day5_wrap.md` — MCP server, open-source repo structure, integration tests

### `audits/`
Internal QA artefacts from the pre-submission audit cycle:

- `AUDIT_REPORT.md` — original judging-grade audit identifying severity-1 and severity-2 issues
- `AUDIT_CLOSURE.md` — closure report confirming all 9 severity-1 + 9 severity-2 items resolved
- `PARTNERSHIP_AUDIT.md` — review of partnership claims, stripped of fabrications
- `E2E_TEST_REPORT.md` — end-to-end integration test summary

### `drafts/`
Working drafts of documentation that became the basis of `trellis.md`:

- `trellis_outline_proposal.md` — original 16-section outline for the master reference
- `trellis_md_drafts/` — current section drafts (Section 1 challenge framing, Section 6 malaria methodology, Section 7 DePIN sensor network)
- `eoi_drafts/` — Expression-of-Interest drafts targeting UNICEF Venture Fund 2026

## Why this exists separately

The repository root carries the runnable platform. This folder carries the *story of how it was built*. Useful for a reviewer who wants to see the engineering arc; not useful for someone who just wants to clone and run.

If you want to delete the lot:

```bash
rm -rf _dev_archive/
```

That will not affect the running stack at all.
