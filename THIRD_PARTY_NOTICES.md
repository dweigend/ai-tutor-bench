# Provenance and third-party notices

David Weigend licenses the project code under MIT. The bundled JSON files under
`src/ai_tutor_bench/` are distributed as benchmark inputs for this release. They
contain project-authored scenarios, scripted dialogue, assessment rules, and
generated schema and hash metadata. The calibration scripts and reference
examples were written for this release. The MIT code license makes no separate
grant over benchmark data.

## Package dependencies

The Python package depends on Pydantic (`MIT`). Build and development
dependencies are listed in `pyproject.toml` and `uv.lock`; their distributions
carry their own licenses.

## Self-hosted documentation assets (`docs/study-v45/vendor/`)

The interactive HTML benchmark reports under `docs/study-v45/` bundle local
copies of third-party client libraries and web fonts so every page works offline
without external CDN requests:

- **Apache ECharts `5.5.1`** (`echarts.min.js`) — licensed under the Apache License, Version 2.0 (`Apache-2.0`).
- **IBM Plex Sans & IBM Plex Mono** (`@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`) — licensed under the SIL Open Font License 1.1 (`SIL OFL 1.1`).
- **Source Serif 4** (`@fontsource-variable/source-serif-4`) — licensed under the SIL Open Font License 1.1 (`SIL OFL 1.1`).

## Data exclusions

Real learner records, full historical model transcripts, raw run logs, identity
mappings, human rater judgments, and private receipts are outside this
distribution. The dated `v4.5` laboratory study report in `docs/study-v45/`
includes aggregated benchmark statistics and three brief illustrative synthetic
fraction-tutoring excerpts for diagnostic transparency. Publish run outputs only
when you have the rights to the visible text and have checked it for identifying
information.
