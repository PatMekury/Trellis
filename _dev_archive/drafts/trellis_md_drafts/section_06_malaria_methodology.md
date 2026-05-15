# Section 6. Climate-sensitive malaria-risk methodology

*Approximately 350 words. Methodology section documenting the malaria layer added to Trellis on 10 May 2026.*

---

Trellis emits a **malaria-risk classification** for each pilot ward, distinct from the generic environmental alert tier. The classification follows the established environmental-driver tradition: it predicts the *environmental likelihood of malaria transmission* in a 4-week window, not case incidence.

**Methodological lineage.** The threshold logic in `model/malaria_risk.py` is aligned with the EPIDEMIA system (Wimberly et al., 2016), which forecasts malaria risk in Ethiopia using rainfall and land-surface temperature anomalies. The same family of approaches is documented in the WHO Climate Change and Human Health programme (2003) and Reiter (2008, *Environmental Health Perspectives*), which establish that *Plasmodium falciparum* extrinsic incubation period is shortest at 22-30°C, that *Anopheles gambiae* survival peaks at 22-28°C, and that monthly rainfall in the 50-300 mm range is optimal for breeding-site formation (too dry suppresses breeding; too wet flushes larvae out).

**Threshold logic.** A ward is classified `likely` when forecast monthly rainfall is in the 50-300 mm optimal range AND mean temperature is in the 22-30°C optimal range AND rainfall exceeds 100 mm (high-signal wetting threshold). It is `possible` when at least one of those is optimal and the other is in the extended acceptable range (rainfall 30-400 mm, temperature 18-33°C). It is `watch` otherwise. The thresholds are constants in `malaria_risk.py:RAIN_*` / `TEMP_*` and are reviewable.

**What this is, and is not.** The malaria layer answers: *given the forecast environmental conditions, is this ward primed for malaria transmission?* It does not answer: *how many cases will occur?* For incidence forecasting, the eighth Trellis predictor — DHIS2 surveillance case data — is required and is currently an open question. This distinction is preserved end-to-end: the surge UI's malaria tab, the SMS template family `render_malaria`, the MCP tool `trellis_malaria_risk`, and the DHIS2 data element `TrellisMlr1` are all framed as *environmental risk*, not incidence.

**Outputs.** The malaria layer produces (a) a per-ward `malaria_risk_tier` field in `forecast_*.json`, (b) a separate column in the DHIS2 dashboard pivot, (c) a `Malaria risk` tab in the surge-planning UI with malaria-specific PHC actions (RDT and ACT pre-positioning, fever-screening protocol briefings), (d) a malaria SMS template family in English and Nigerian Pidgin, and (e) the MCP tool `trellis_malaria_risk` for AI-agent integration.

---

## Provenance and track-changes record

This section was added on 10 May 2026 in response to Patrick's request to extend Trellis with explicit malaria-risk modelling, after a discussion of the UNICEF Climate Ventures challenge prompt:

> Climate-sensitive forecasting models for infectious diseases (e.g. malaria, dengue, etc.) and heat-related illnesses, linked to public health decision-making and surge planning (such as DHIS2).

Scope decisions explicitly applied:

- **Malaria added** as a first-class disease layer with its own classifier, dashboard column, surge tab, SMS templates, and MCP tool.
- **Heat-related illness deferred**, per Patrick's instruction (10 May 2026).
- **Dengue out of scope**, per Patrick's instruction. Aedes vectors are present in Niger Delta but Trellis has not been targeted at dengue specifically and would require dengue surveillance data integration to claim coverage.
- **Compartmental transmission models (SIR/SEIR) deliberately not implemented.** Trellis uses the environmental-driver tradition (EPIDEMIA, EWARS), not vector dynamics modelling. A reviewer reading "epidemiological modelling on disease spread" strictly as transmission modelling will see this as a scope choice; the lineage citations show this is recognised epidemiology.

## Word count

Section 6 body: 348 words. Provenance section: 174 words.
