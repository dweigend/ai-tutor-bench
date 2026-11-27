# AI Tutor Bench

Reproducible evaluation of AI tutor behavior with versioned scenarios and rubrics. It checks whether a tutor gives useful hints, responds to mistakes, and avoids giving away solutions. The benchmark measures tutor behavior. Learning impact still requires a separate study.

[AI Tutor Core](https://github.com/dweigend/ai-tutor-core) · [AI Tutor App](https://github.com/dweigend/ai-tutor-app)

## Research question and design

`ai-tutor-bench` evaluates whether a tutoring system diagnoses a learner's obstacle from dialogue cues, selects a fitting pedagogical move, leaves the next solution step open for the learner, checks understanding through observable attempts, and returns to the agreed goal after diversions.

Execution is model-neutral, frozen, and offline-capable:

- **Frozen scenario plan (`161` cells at `seed=0`):** Each run dispatches the same typed `CellPlan` across three single-turn fraction fixtures (`fixture`), thirty single-turn GT1–GT10 scenarios in [gt1-gt10-katalog.json](src/ai_tutor_bench/v5/szenarien/gt1-gt10-katalog.json) (`10` synthetic calibration cases and `20` main measurement cases), and two scripted 32-turn drift episodes in [drift-szenarien.json](src/ai_tutor_bench/v5/drift/drift-szenarien.json) with one learner cell and one tutor cell per turn (`128` cells). Scripted learner turns can branch on the preceding tutor reply.
- **Signal-mode matrix and rubric:** [signal-modus-matrix.json](src/ai_tutor_bench/v5/schema/signal-modus-matrix.json) maps observed learner signals to permitted modes (`RUECKFRAGE_SCAFFOLD`, `ERKLAEREN`, `VISUALISIEREN`, `PRUEFEN`, `ZIEL_STEUERN`, `MOTIVIEREN`) and prohibited modes (`SERVICE`, `TELLING`). [rubric.json](src/ai_tutor_bench/v5/schema/rubric.json) specifies five behavioral criteria (`diagnosis`, `fit`, `disclosure`, `evidence`, `goal_tracking`) rated `0`, `1`, `2`, or `null` when not observable, paired with deterministic surface detectors in [detektoren-v1.json](src/ai_tutor_bench/analyse/detektoren-v1.json).
- **Blind projection and explicit denominators:** Completed runs seal raw records in a local `private/` directory and project all `161` planned cells into a sorted, metadata-free `public/blind.jsonl` export that replays without model credentials or dispatch.

## Quick start

Use Linux with Python 3.12 or later and [uv](https://docs.astral.sh/uv/). Install the locked environment, check the frozen asset inventory and revision digests, and run both deterministic offline adapters (`fixture` and `alternate`) in separate output directories:

```sh
uv sync --locked
uv run --locked ai-tutor-bench check-freeze
uv run --locked ai-tutor-bench check-revisions
uv run --locked ai-tutor-bench dry-run --adapter fixture --output-dir runs/fixture
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/alternate
```

After dependency installation, these commands require no network access or API credentials, incur `0` USD (`cost_microusd: 0`), and also run from an empty working directory via the installed `ai-tutor-bench` entry point. `fixture` and `alternate` execute the identical 161-cell plan under distinct `run_id` digests and produce distinct tutor responses for offline A/B verification.

Each attempt is written to a start journal before dispatch so runs can pause and resume deterministically without re-dispatching settled cells:

```sh
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/resume-check --stop-after 11
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/resume-check
```

Verify a public blind export on its own, reconcile an export against its local `private/` directory, and run the test suite:

```sh
uv run --locked ai-tutor-bench replay --public-dir runs/fixture/public
uv run --locked ai-tutor-bench replay --adapter alternate --public-dir runs/alternate/public --private-dir runs/alternate/private
uv run --locked pytest
```

## Freeze, revisions, and citation

`check-freeze` validates the packaged asset tree against [freeze.json](src/ai_tutor_bench/v5/schema/freeze.json) (`freeze_sha256`: `7d1895270d7c82994afa22bcbfaccc96e9b0dc3b3d0f31da0805b8a8e638ced2`) and rejects missing, extra, modified, or symlinked files.

`check-revisions` reports three independent SHA-256 digests so changes to downstream analysis do not invalidate sealed runs or exports:

- `execution_revision`: suite construction, adapters, and execution assets on the dispatch path.
- `export_revision`: raw-row validation, blind projection, receipt sealing, and replay verification.
- `analysis_revision`: rubric, signal-mode schema, drift scoring, and surface detectors.

Cite David Weigend, *AI Tutor Bench*, version 0.1.0, and record the Git commit SHA, `freeze_sha256`, adapter identity, seed, and the `execution_revision`, `export_revision`, and `analysis_revision` digests alongside reported runs.

## Denominators, failure modes, and interpretation limits

- **Planned vs. observed denominators:** Every planned cell stays in the denominator (`161` rows in `public/blind.jsonl`). Public replay checks the sidecar SHA-256, canonical JSON formatting, unique 32-hex `blind_id` tokens, and expected row count, reporting `planned`, `visible`, and `without_visible_text`.
- **Failure and censoring states:** Adding `--private-dir` verifies `public/blind.jsonl` against `private/export/raw.jsonl` and `receipt.json` and breaks down all seven cell outcomes: `ok`, `abgeschnitten` (truncated), `leer` (empty), `technisch` (technical failure), `abgebrochen` (started in the journal without settled completion), `zensiert` (remaining episode or run cells censored after an upstream failure, budget cap, or subscription censure limit), and `nicht_gestartet` (unstarted). Only `ok` and `abgeschnitten` cells with verified adapter identity emit visible text; all other states emit `text: null` so failed or censored cells never drop out of the denominator.
- **Blind projection boundaries:** `public/` contains only lexicographically sorted `{"blind_id", "text"}` rows in `blind.jsonl` and `blind.jsonl.manifest.json`. Sorting prevents file order from exposing arm or case sequence, and fresh `blind_id` values are generated when sealing the export. Raw payloads, model identities, `run_id`, `cell_id`, episode hashes, attempt logs, and local receipts stay in `private/`. Export and public replay reject visible text matching local filesystem path patterns or bundled adapter identifiers. Export and replay with `--private-dir` also check the bound adapter identities, including custom model identifiers, as well as the run, cell, and episode identifiers recorded for that run. An `identity_violation` blocks publication. Because open-ended model text can still contain unforeseen identifying details, keep `private/` local and inspect visible text before publishing external runs.
- **Interpretation limits:** The bundled `fixture` and `alternate` adapters test execution, accounting, blind projection, and replay; they provide no model ranking. Formal human judge calibration for the rubric remains open. Behavioral scores on simulated dialogues describe tutoring process quality and do not establish human learning gains, retention, or transfer.

## Scope boundaries, license, and provenance

Project code and tests are licensed under the [MIT License](LICENSE). Bundled JSON catalogs, schemas, and calibration files are distributed as project-authored benchmark inputs for this release; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance terms and third-party dependency notices.

This repository contains only synthetic and project-authored public scenarios, assessment schemas, and deterministic offline adapters. It excludes private learner dialogues, raw or blind evaluation bundles from external model runs, human rater judgments, and third-party datasets or model weights.

## AI disclosure

AI coding tools assisted with implementation, refactoring, synthetic calibration fixtures, tests, and documentation under human specification, review, and verification.
