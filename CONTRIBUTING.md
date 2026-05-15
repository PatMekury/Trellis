# Contributing to Trellis

Trellis is an open-source platform under active early-stage development. Contributions are welcome.

## What needs help right now

In rough priority order:

1. **DHIS2 metadata-pack improvements.** The current org-unit hierarchy generated from GRID3 boundaries is a starting point; richer DHIS2 implementations would benefit from program indicators, predefined visualisations, and tracker programs.
2. **Local-language SMS templates.** Currently English and Nigerian Pidgin. Useful next: Yoruba, Igbo, Edo, Urhobo.
3. **Hardware additions.** CO₂, PM₁, additional NO₂ cells, and an outdoor-rated enclosure design.
4. **Forecast model improvements.** Multi-year cross-validation refinements, lead-time-conditioned ensemble, calibration to ground-truth case data when it becomes accessible.
5. **DHIS2 dashboard widgets.** The current dashboard is a custom HTML/JS app; a DHIS2 Pivot Table layer or Visualizer integration would lower the deployment friction.
6. **Multi-state extension.** The pipeline is region-agnostic; pulling 5 LGAs in Bayelsa or Rivers state should require only a config change. Worth verifying.

## How to contribute

### Pull requests

1. Fork the repo
2. Create a feature branch
3. Make your change with tests if applicable
4. Submit a PR explaining the why and the verification

Code style: follow the surrounding code's conventions (Python: black + isort; JS: standard browser-vanilla ES2020).

### Issues

For bug reports, include:
- The piece of the platform affected (`backend/`, `dhis2/`, etc.)
- A minimal reproduction
- The expected behaviour vs what you saw
- Your environment

For feature requests, include the use case and the user it serves.

### Documentation

Documentation contributions are first-class. The data cards in `data/*/` and the per-day sprint wraps are designed to be read by people who arrived after the fact; if anything is unclear, fix it.

## What we will not accept

- **Closed-source dependencies in the deployed stack.** Trellis ships open-source end to end. A PR that introduces a closed-source library to the deployed code path will be declined.
- **Unverified statistics.** Numbers in EOI drafts and data cards must cite their source. Don't add a number without showing where it came from.
- **Code that imports private health data.** This repo is open-source. Real ministry data lives in the ministry's DHIS2; the dashboard *queries* it but never bundles it.
- **Marketing copy.** Trellis documents are written in direct, professional, non-jargon English. PRs that rewrite docs in marketing-speak will be reverted.

## Code of conduct

See `CODE_OF_CONDUCT.md`. tl;dr: be kind, be honest, focus on the work.

## Maintainers

This repository does not yet have a confirmed maintainer team beyond the project lead. Maintainers are added publicly via PR to this file once they have demonstrated sustained contribution.

## Licensing

By contributing to Trellis, you agree that your contributions will be licensed under the same terms as the surrounding code: MIT for software, GPL-3.0 for DHIS2 connectors, CC-BY 4.0 for data and docs, TAPR Open Hardware for firmware.
