# AI Tutor Bench

Reproducible evaluation of AI tutor behavior using versioned scenarios, deterministic surface checks, and blind exports (an independent open-source harness by David Weigend, distinct from Scale AI's TutorBench). The benchmark tests whether a tutoring system diagnoses a learner's obstacle, chooses a fitting pedagogical move, avoids giving away solutions, checks understanding, and returns to the agreed learning goal after diversions.

> **Scope boundary:** `ai-tutor-bench` measures **tutoring process behavior in simulated dialogues**. It does **not** measure human learning gains, retention, or transfer, which require a separate study with human learners.

[AI Tutor Core](https://github.com/dweigend/ai-tutor-core) · [AI Tutor App](https://github.com/dweigend/ai-tutor-app) · [Reproducibility & Adapter Guide](docs/reproducibility.md) · [v4.5 Study Paper](docs/study-v45/paper.md)

## What is in this repository (`v5` suite vs. dated `v4.5` study report)

This repository ships **software package `0.1.0`** and the frozen **`v5` benchmark suite (`161` planned cells at `seed=0`)** together with two built-in deterministic offline adapters (`fixture` and `alternate`) so you can verify execution, accounting, blind projection, and replay at **$0 cost** with no API credentials.

- **Runnable harness (`v5` offline suite):** `3` single-turn fraction fixtures, `30` single-turn GT1–GT10 scenarios in [`gt1-gt10-katalog.json`](src/ai_tutor_bench/v5/szenarien/gt1-gt10-katalog.json) (`10` calibration cases and `20` main cases), and `2` scripted 32-turn drift episodes in [`drift-szenarien.json`](src/ai_tutor_bench/v5/drift/drift-szenarien.json) (`128` learner + tutor cells; scripted learner turns can branch on the previous tutor reply).
- **Dated `v4.5` laboratory study documentation (`docs/study-v45/`):** Published alongside the `v5` software harness for transparency — [Technical Paper (Markdown)](docs/study-v45/paper.md), [Executive Results Report (5 interactive figures, HTML)](docs/study-v45/results/index.html), [Interactive Data Explorer (HTML)](docs/study-v45/explorer/index.html), and [Technical Paper (HTML)](docs/study-v45/paper/index.html). **The dated `v4.5` empirical laboratory results come from an earlier experimental matrix and cannot be reproduced by running the `v5` offline suite here.**
- **Not included in this repository:** Private learner dialogues, full raw or blind evaluation bundles from external LLM runs, human rater judgments, third-party datasets, and model weights (including the separate 9B LoRA scaffolding-coach training track).

## One concrete scenario example

Scoring combines two distinct specifications:
1. **Per-scenario catalog metadata** ([`gt1-gt10-katalog.json`](src/ai_tutor_bench/v5/szenarien/gt1-gt10-katalog.json)) defines each dialogue prefix, learner signal, allowed/prohibited pedagogical modes (mapped in [`signal-modus-matrix.json`](src/ai_tutor_bench/v5/schema/signal-modus-matrix.json)), and the scenario-specific binary check question (`prueffrage_binaer`).
2. **Global rubric** ([`rubric.json`](src/ai_tutor_bench/v5/schema/rubric.json)) independently defines five behavioral criteria (`diagnosis`, `fit`, `disclosure`, `evidence`, `goal_tracking`), each rated `0`, `1`, `2`, or `null` when not observable, paired with deterministic surface detectors in [`detektoren-v1.json`](src/ai_tutor_bench/analyse/detektoren-v1.json).

Example from `gt1-gt10-katalog.json` (`gt1-public-regenmesser`, synthetic German calibration case with English gloss):

- **Learning goal:** Measure rainfall as height (*„Niederschlag als Höhe messen.“*)
- **Prefix:** Learner wants to read yesterday's rain in the measuring cup (*Messbecher*); tutor prompts comparing the water level to the zero mark.
- **Trigger turn (`signal: exkurs` / off-topic diversion):** *„Apropos Regen, wieso schlafen manche Tiere bei Gewitter einfach weiter?“* (*"Speaking of rain, why do some animals keep sleeping through thunderstorms?"*)
- **Allowed mode:** `ZIEL_STEUERN` (acknowledge briefly and guide back to reading the scale).
- **Prohibited modes:** `SERVICE`, `TELLING` (switching to an explanation of animal behavior).
- **Scenario check question (`prueffrage_binaer`):** *„Greift die Antwort das konkrete Lernsignal auf?“* (*"Does the reply address the concrete learner signal?"*)

## Quick start (offline, $0)

Requires Linux, Python 3.12+, and [uv](https://docs.astral.sh/uv/). After `uv sync --locked`, every command below runs offline with `cost_microusd: 0` and no API keys:

```sh
uv sync --locked
uv run --locked ai-tutor-bench check-freeze
uv run --locked ai-tutor-bench check-revisions
uv run --locked ai-tutor-bench dry-run --adapter fixture --output-dir runs/fixture
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/alternate
uv run --locked ai-tutor-bench replay --public-dir runs/fixture/public
```

Both built-in adapters execute the identical 161-cell plan under distinct `run_id` digests and emit distinct responses for offline A/B checks. Run `uv run --locked pytest` to execute the test suite.

**Denominator rule:** Every one of the `161` planned cells stays in the denominator of `public/blind.jsonl`. Only `ok` and `abgeschnitten` (truncated) cells with verified adapter identity emit visible text; failed, aborted, or censored cells emit `text: null` so drop-outs never vanish silently from reported counts.

## Connecting your own model and deep reproducibility

To evaluate your own tutor model, implement `AdapterProtocol` (`ai_tutor_bench.runtime.v5.contracts`) and pass it to `run_benchmark(...)` (`ai_tutor_bench.runtime.v5.workflow`) so your outputs flow through the same frozen `CellPlan`, start journal, blind projection, and replay verifier.

See [Reproducibility, Adapter Contract, and Failure States](docs/reproducibility.md) for the exact `AdapterProtocol` signature, a runnable offline custom-adapter example, pause/resume (`--stop-after`), private reconciliation (`--private-dir`), all seven cell states, and the three independent SHA-256 revision digests.

## Freeze, citation, and interpretation limits

- **Frozen asset digest:** `check-freeze` verifies all packaged benchmark assets against [`freeze.json`](src/ai_tutor_bench/v5/schema/freeze.json) (`freeze_sha256`: `7d1895270d7c82994afa22bcbfaccc96e9b0dc3b3d0f31da0805b8a8e638ced2`) and rejects missing, extra, modified, or symlinked files.
- **No built-in ranking:** The bundled `fixture` and `alternate` adapters verify execution, accounting, blind projection, and replay only. Formal human judge calibration for the rubric remains open.
- **Citation:** Cite David Weigend, *AI Tutor Bench*, version `0.1.0`, and record the Git commit SHA, `freeze_sha256`, adapter identity, seed, and the three digests from `check-revisions` alongside any reported run.

```bibtex
@software{weigend2026aitutorbench,
  author  = {Weigend, David},
  title   = {AI Tutor Bench},
  version = {0.1.0},
  year    = {2026},
  url     = {https://github.com/dweigend/ai-tutor-bench}
}
```

## License and AI disclosure

Project code and tests are licensed under the [MIT License](LICENSE). Bundled JSON catalogs, schemas, and calibration fixtures are project-authored benchmark inputs for this release; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance, third-party dependency notices, and licenses of the self-hosted documentation libraries in `docs/study-v45/vendor/`.

AI coding tools assisted with implementation, refactoring, synthetic calibration fixtures, tests, and documentation under human specification, review, and verification.
