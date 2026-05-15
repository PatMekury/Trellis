# Audit — unconfirmed partnership claims across Trellis artefacts

**Date:** 9 May 2026
**Prompted by:** Patrick's directive on 9 May 2026 — "please don't believe any pending partnership in the .md file ask me first."
**Scope:** every `.md` file under `Trellis/` produced in this session.
**Purpose:** surface every place that implies a partner has agreed to anything, so Patrick can correct or confirm.

## Summary

I scanned 22 markdown files across `outreach/`, `data/`, `dhis2/`, `eoi_drafts/`, `trellis_md_drafts/`, `model/`, and the project root. Found **20 distinct claims** across **9 files** that assume engagement with a partner who has not (to my knowledge) confirmed engagement.

The partners that recur:

| Partner | How it appears in artefacts | Status I should ask Patrick about |
|---|---|---|
| **Contrad Community Development Group** | "implementing community partner", host of 5 community sensor sites, recipient of LoI #1 | Unknown |
| **Delta State Ministry of Health (SMOH)** | DHIS2 data provider, EOI co-signatory, MOU counterparty | Unknown |
| **NPHCDA** (Federal PHC agency) | host of 10 PHC sensor sites, LoI recipient | Unknown |
| **Delta State Universal Basic Education Board (SUBEB)** | host of 10 school sensor sites, LoI recipient | Unknown |
| **University of Port Harcourt + Niger Delta University** | "target academic partners" for sensor calibration loaners | Unknown |
| **HISP West and Central Africa** | named in TRELLIS_INSTRUCTIONS.md as a target NGO | Unknown |
| **Co-PI** | repeatedly referenced as a person to be confirmed | Unknown |

The findings below are organised by severity. **Severity-1** items materially affect what Trellis can claim in formal communication. **Severity-2** affects internal documents that frame the project narrative. **Severity-3** is low-stakes phrasing that should still be cleaned up but does not damage outreach.

---

## Severity 1 — affects formal outreach

### S1-1. `outreach/loi_contrad_cdg.md`, line 25

> "We would like to invite Contrad CDG to be the implementing community partner for these five sites: identifying a custodial host in each ward, coordinating community awareness, and supporting routine sensor maintenance."

**Assumes:** Contrad CDG was selected from a set of candidates and is the right counterparty for the role.

**Question for Patrick:** Have you had any prior contact with Contrad Community Development Group? If not, the letter should not call them "the implementing community partner" — it should propose a meeting to discuss whether the role suits them.

---

### S1-2. `outreach/loi_README.md`, lines 9–14 and 35

> "| 1 | Contrad Community Development Group | Endorse 5 community node sites | trellis.md final, this LoI |"
> "| 4 | Delta State Ministry of Health | DHIS2 read access; pilot programmatic endorsement | Highest stakes; send last, after at least one of the above has responded |"
> "Sending in this order builds a paper trail that strengthens each subsequent letter."
> "co-PI name (TBD)"

**Assumes:** there is a coordinated outreach sequence, that responses from earlier partners will exist, that there is a co-PI position to fill at all.

**Question for Patrick:** Is there a defined co-PI position? Are you currently in conversation with any of the four LoI recipients?

---

### S1-3. `outreach/attachment_ward_list.md`, lines 13, 28, 43

> "### PHC nodes (10 — host: NPHCDA-listed primary health centres)"
> "### School nodes (10 — host: Delta State Universal Basic Education Board primary schools)"
> "### Community nodes (5 — host: Contrad Community Development Group)"

**Assumes:** these three institutions are the hosts. Reads as a fait accompli.

**Question for Patrick:** Should these say "proposed host: …" or be left blank pending confirmation?

---

### S1-4. `outreach/loi_nphcda.md`, line 25

> "The exact host PHC in each ward will be identified jointly with NPHCDA's Delta State coordinating office during Phase 1."

**Assumes:** NPHCDA's Delta coordinating office will be in scope. Per Patrick's rule, even this should be conditional on NPHCDA's response to the letter.

**Suggested fix:** "The exact host PHC in each ward will be identified during Phase 1 in collaboration with whichever institutional partner endorses this proposal."

---

### S1-5. `outreach/loi_smoh.md`, lines 13, 20

> "I am writing to request two things at this stage: 1. **Ministerial endorsement** ..."
> "We propose that any data-sharing arrangement be governed by an MOU that the Ministry drafts and Trellis co-signs."

**Assumes:** the Trellis project is a real entity that can co-sign an MOU. Per project instructions, Nigerian incorporation is *pending* and per Patrick's new rule, "pending" cannot be claimed without confirmation.

**Question for Patrick:** What is the actual incorporation status? The letter should reflect that.

---

## Severity 2 — internal-document framing

### S2-1. `data/siting/sensor_allocation_proposal.md`, line 116

> "Final node placement must be at a specific named PHC, school, or community building chosen by the implementing partners (Contrad CDG, Delta SMOH, NPHCDA, school custodians) during Phase 1 deployment."

**Assumes:** these four are the implementing partners.

**Suggested fix:** "Final node placement must be at a specific named PHC, school, or community building chosen during Phase 1 in collaboration with whichever institutional partner endorses each channel."

---

### S2-2. `data/siting/sensor_allocation_proposal.md`, line 135

> "the project can approach NPHCDA for the 10 PHC node hosts, the Delta State Education Board for the 10 school hosts, and Contrad CDG for the 5 community sites."

**Assumes:** the three named institutions are the appropriate first approach. Even "can approach" implies prior identification of these as the right targets.

**Suggested fix:** "Phase 1 includes formal outreach to the institutional partner that will host each channel — to be identified jointly with the project lead."

---

### S2-3. `trellis_md_drafts/section_07_depin_sensor_network.md`, lines 15, 32

Body text mentions: "in-situ co-location with one mobile reference instrument per LGA — to be loaned for a four-week shakedown period via target academic partners (University of Port Harcourt and Niger Delta University)"

Caveat note says: "University of Port Harcourt and Niger Delta University as calibration loaners are listed as **target** partners, not confirmed."

**Assumes:** these two universities are the target academic partners. Per the new rule, "target" itself is too strong.

**Suggested fix:** Remove the named universities from the body text. Replace with "academic calibration loaner — institution to be identified." The caveat note can stay but should also drop the named universities.

---

### S2-4. `trellis_outline_proposal.md`, lines 142, 158, 202

> "Phase 1 deliverables now include: ...; co-PI confirmed; ..."
> "Patrick (lead, currently named) plus the to-be-confirmed co-PI plus the implementing community partner (Contrad CDG, contingent on the LoI response)."
> "**At least one signed LoI** — preferably from Contrad CDG, since that's the easiest first to obtain ..."

**Assumes:** Contrad CDG is the easiest first responder, and a co-PI process is in motion.

**Suggested fix:** Drop named partners from the open-questions list. "Co-PI" stays as an open question. "Implementing community partner" stays as an open question. No names.

---

### S2-5. `data/health/health_DATA_CARD.md`, line 130

> "Hospital-level bed inventory comes from the State Ministry of Health, not GRID3. Add as a Delta-SMOH partnership deliverable."

**Assumes:** Delta SMOH partnership is in train.

**Suggested fix:** "Add as a deliverable conditional on a future state-level data-sharing agreement."

---

### S2-6. `data/population/population_DATA_CARD.md`, line 107

> "Cross-check against the official National Population Commission projections at admin-3 once accessed via SMOH partnership."

**Assumes:** SMOH partnership will provide NPC access.

**Suggested fix:** "Cross-check against the official NPC projections once that data source becomes accessible to the project."

---

### S2-7. `data/predictors/predictors_DATA_CARD.md`, line 114

> "| 8 | DHIS2 historical health outcomes | Not yet accessible. Requires Delta SMOH partnership. |"

**Assumes:** the path is specifically through Delta SMOH.

**Suggested fix:** "Not yet accessible. Requires a state-level data-sharing arrangement with the relevant ministry of health."

---

### S2-8. `model/day1_skill_report.md`, line 86

> "These should be calibrated to actual childhood-respiratory case data once SMOH partnership lands."

**Suggested fix:** "These should be calibrated to actual childhood-respiratory case data once such data becomes accessible to the project."

---

### S2-9. `dhis2/SETUP_LOCAL_DHIS2.md`, lines 5, 233, 253

> "Delta SMOH, FMOH NHMIS, HISP WCA sandbox, anywhere"
> "the historical childhood malaria, ARI, and immunisation data is owned by Delta SMOH and only available once that partnership is confirmed."
> "the Delta SMOH integration is a single configuration change away"

**Assumes:** Delta SMOH is the named eventual partner.

**Suggested fix:** rename the references to "any future state-level DHIS2 instance" without specifying SMOH or HISP WCA by name.

---

## Severity 3 — low-stakes wording

### S3-1. `data/health/health_DATA_CARD.md`, line 22

> "GRID3 Nigeria, in collaboration with the Federal Ministry of Health and the National Primary Health Care Development Agency (NPHCDA)."

This describes the *publisher* of the dataset (GRID3 + FMOH + NPHCDA), not Trellis's partnerships. **Not a violation** — leave as is.

---

### S3-2. `outreach/loi_README.md`, line 23

> "**No unconfirmed partnerships.** No letter implies that any of the other three partners has already endorsed Trellis."

This is a *self-imposed rule* in the README that says letters don't imply partnerships have endorsed. Ironically, the README itself violates the spirit by listing those four institutions as "the partners" the project is sending to. **Suggested fix:** rename "partners" to "candidate organisations being approached."

---

## Recommended next step

Three files have the most painful violations. They are the four LoIs and the LoI README. I propose:

1. **Hold the LoIs as drafts** — don't send them as is. They imply a Trellis project posture (incorporated, has co-PI, in conversation with these four institutions) that has not been confirmed.
2. **Rewrite each LoI** under one explicit assumption per letter, clearly stated at the top of the file. For example, the Contrad letter would say: "ASSUMES: no prior contact with Contrad CDG. Letter is a cold introduction." The SMOH letter would say: "ASSUMES: Trellis is not yet incorporated; Patrick writes as project lead in personal capacity."
3. **Move the partnership-naming claims out of internal documents** (siting proposal, trellis_outline_proposal.md, section_07) and into one explicit "assumed partners — TO CONFIRM" file at the project root, so the rest of the docs can stay clean.

Per the permission rule, I will not edit any of these files until Patrick confirms which fixes to apply.

## What this audit does not cover

- **TRELLIS_INSTRUCTIONS.md** is the project's master operating contract. It contains many of the partner names that propagated into my artefacts (Contrad CDG, HISP WCA, UPTH, etc.). I did not modify or audit that file because Patrick owns it. Once Patrick is willing to specify which of those names are actually engaged and which are aspirational, the audit can be fed back into TRELLIS_INSTRUCTIONS.md.
- **trellis.md** itself does not yet exist, so no audit there.
- **Code files (.py, .html, .json)** were not scanned for partnership claims because they don't contain narrative; only metadata (model id, source attribution).
