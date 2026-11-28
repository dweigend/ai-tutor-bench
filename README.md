# AI Tutor Bench

Reproducible evaluation of AI tutor behavior using versioned scenarios, deterministic checks, and blind exports. It tests whether a tutor diagnoses a learner's obstacle, chooses a fitting move, avoids giving away solutions, checks understanding, and returns to the learning goal after diversions.

> **Scope:** `ai-tutor-bench` measures **tutoring behavior in simulated dialogues**, not human learning gains, retention, or transfer.

[Live v4.5 Study Results & Explorer](https://dweigend.github.io/ai-tutor-bench/) · [Reproducibility & Adapter Guide](docs/reproducibility.md) · [v4.5 Study Paper](docs/study-v45/paper.md)

## Repository contents

This repository ships the runnable **`v5` offline benchmark suite** (`161` planned cells, `seed=0`, built-in `fixture` and `alternate` adapters) alongside the dated **`v4.5` laboratory study documentation** ([Results](https://dweigend.github.io/ai-tutor-bench/study-v45/results/), [Explorer](https://dweigend.github.io/ai-tutor-bench/study-v45/explorer/), [Paper](https://dweigend.github.io/ai-tutor-bench/study-v45/paper/), also viewable offline via `docs/index.html`). The published `v4.5` study used an earlier experimental matrix and cannot be reproduced by running the `v5` offline suite here.

## One concrete scenario example

Each scenario pairs catalog rules ([`gt1-gt10-katalog.json`](src/ai_tutor_bench/v5/szenarien/gt1-gt10-katalog.json)) with a 5-criterion rubric ([`rubric.json`](src/ai_tutor_bench/v5/schema/rubric.json)) and deterministic text checks. Example calibration case (`gt1-public-regenmesser`, German with English gloss):

- **Learning goal:** Measure rainfall as height (*„Niederschlag als Höhe messen.“*)
- **Context:** The learner wants to measure yesterday's rain with a measuring cup; the tutor asks how the water level compares to the zero mark.
- **Learner diversion (`exkurs`):** *„Apropos Regen, wieso schlafen manche Tiere bei Gewitter einfach weiter?“* (*"Speaking of rain, why do some animals keep sleeping through thunderstorms?"*)
- **Target move:** Acknowledge briefly and steer back to reading the scale (`ZIEL_STEUERN`), without launching into an explanation of animal behavior (`SERVICE`, `TELLING`).
- **Binary check question:** *„Greift die Antwort das konkrete Lernsignal auf?“* (*"Does the reply address the concrete learner signal?"*)

## Quick start

Requires Linux, Python 3.12+, and [uv](https://docs.astral.sh/uv/). After installation, every command below runs offline with no API keys:

```sh
uv sync --locked
uv run --locked ai-tutor-bench check-freeze
uv run --locked ai-tutor-bench check-revisions
uv run --locked ai-tutor-bench dry-run --adapter fixture --output-dir runs/fixture
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/alternate
uv run --locked ai-tutor-bench replay --public-dir runs/fixture/public
```

Run `uv run --locked pytest` to execute the test suite. Every one of the `161` planned cells stays in the `public/blind.jsonl` denominator: failed or censored cells emit `text: null` so drop-outs never vanish silently.

## Evaluate your own model

Implement `AdapterProtocol` and pass your adapter into `run_benchmark(...)` — see the complete runnable example, revision digests, pause/resume workflow, and failure states in the [Reproducibility & Adapter Guide](docs/reproducibility.md).

## Citation, license, and AI disclosure

Bundled adapters verify execution and blind replay only; formal human judge calibration remains open. Cite David Weigend, *AI Tutor Bench* (`0.1.0`) together with commit SHA, `freeze_sha256`, adapter identity, seed, and `check-revisions` digests:

```bibtex
@software{weigend2026aitutorbench,
  author  = {Weigend, David},
  title   = {AI Tutor Bench},
  version = {0.1.0},
  year    = {2026},
  url     = {https://github.com/dweigend/ai-tutor-bench}
}
```

Code and tests are [MIT-licensed](LICENSE); bundled benchmark inputs and self-hosted documentation licenses are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). AI coding tools assisted with implementation, fixtures, tests, and documentation under human specification and review.
