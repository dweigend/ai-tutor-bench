# Reproducibility, Adapter Contract, and Failure States (`ai-tutor-bench` v5)

Operational reference for `ai-tutor-bench` (`0.1.0`, Suite `v5`): custom adapters, revision digests, resume journaling, cell states, and blind exports.

## Connecting a custom tutor adapter

Implement `AdapterProtocol` from [`ai_tutor_bench.runtime.v5.contracts`](../src/ai_tutor_bench/runtime/v5/contracts.py) and pass it into `run_benchmark(...)`:

```python
class AdapterProtocol(Protocol):
    @property
    def kind(self) -> AdapterKind: ...
    @property
    def identity(self) -> str: ...
    def reserve(self, cell: PlannedCell) -> Microusd: ...
    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt: ...
```

Replacing `(OFFLINE_ARM, TUTOR_ROLE)` routes the **97 tutor cells** to your adapter while the built-in learner adapter runs the **64 scripted learner cells**. `reserve()` runs before dispatch so caps can censor remaining cells cleanly; `execute()` must return a `SettledAttempt` with `BillingReport` (even on provider failure), while unhandled exceptions leave the cell unsettled for safe resume.

This complete offline example runs as-is on a clean checkout of `ai-tutor-bench 0.1.0`:

```python
from pathlib import Path
from typing import ClassVar, Literal

from ai_tutor_bench.runtime.core.cell_plan import PlannedCell
from ai_tutor_bench.runtime.core.freeze import check_freeze
from ai_tutor_bench.runtime.core.result_settlement import (
    AttemptResult,
    BillingReport,
    CellOutcome,
    SettledAttempt,
)
from ai_tutor_bench.runtime.core.start_journal import Microusd, StartEvent
from ai_tutor_bench.runtime.v5.contracts import EpisodeHistory
from ai_tutor_bench.runtime.v5.suite import load_suite
from ai_tutor_bench.runtime.v5.workflow import run_benchmark
from ai_tutor_bench.v5.drift.trockenlauf import OFFLINE_ARM, TUTOR_ROLE


class MyTutorAdapter:
    kind: ClassVar[Literal["fixture"]] = "fixture"
    identity: ClassVar[str] = "my-org/my-tutor-v1"

    def reserve(self, cell: PlannedCell) -> Microusd:
        # Return maximum expected cost in micro-USD before dispatch (0 for local/offline)
        return 0

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        text = "What do you predict happens next, and why?"
        return SettledAttempt(
            result=AttemptResult(
                key=start.key,
                outcome=CellOutcome.OK,
                raw={"response": text},
                visible_text=text,
                finish_reason="stop",
            ),
            billing=BillingReport(is_byok=False, reported_microusd=0),
        )


freeze_sha256 = check_freeze()
spec, adapters = load_suite(freeze_sha256, "fixture")
adapters[(OFFLINE_ARM, TUTOR_ROLE)] = MyTutorAdapter()

run_dir = Path("runs/my-run")
run_dir.mkdir(parents=True, exist_ok=True)
receipt = run_benchmark(
    spec,
    adapters,
    private=run_dir / "private",
    public=run_dir / "public",
)
```

Supported `AdapterKind` values are `"fixture"`, `"openrouter"`, `"simulator-cli"`, `"vllm"`, and `"peft"`.

## Three independent revision digests

`uv run --locked ai-tutor-bench check-revisions` hashes three surfaces separately so downstream analysis edits do not invalidate sealed runs:

- **`execution_revision`:** Suite construction, adapters, and dispatch assets.
- **`export_revision`:** Raw validation, blind projection, sealing, and replay.
- **`analysis_revision`:** Rubric, signal-mode matrix, drift scoring, and surface detectors.

Cite all three digests with the Git commit SHA, `freeze_sha256`, adapter identity, and `seed`.

## Pause, resume, and private reconciliation

Each attempt is journaled before dispatch; re-running with the same `--output-dir` resumes cleanly without re-running settled cells:

```sh
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/resume-check --stop-after 11
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/resume-check
```

Reconcile the blind export against its local `private/` directory:

```sh
uv run --locked ai-tutor-bench replay \
  --adapter alternate \
  --public-dir runs/resume-check/public \
  --private-dir runs/resume-check/private
```

## Planned vs. observed denominators and cell states

Public replay verifies the manifest, canonical JSON, unique `blind_id` tokens, and full row count (`161`). Adding `--private-dir` reports all seven states: only `ok` and `abgeschnitten` emit visible text; all five failure/censoring states emit `text: null` so drop-outs remain in the planned denominator.

| State | Meaning | Visible text? |
|---|---|---|
| `ok` | Completed cleanly with verified adapter identity | Yes |
| `abgeschnitten` | Truncated response with verified adapter identity | Yes |
| `leer` | Empty model output | No |
| `technisch` | Technical or transport failure | No |
| `abgebrochen` | Started in journal without settled completion | No |
| `zensiert` | Remaining cells censored after upstream error or cap | No |
| `nicht_gestartet` | Never started | No |

## Blind-projection boundaries

`public/` stores only lexicographically sorted `{"blind_id", "text"}` rows and a SHA-256 manifest, hiding arm and scenario order. Raw payloads, model identities, `run_id`, `cell_id`, and receipts stay in `private/`, and replay blocks publication on any `identity_violation` (local paths, adapter/model IDs, or run tokens). Because free text can still leak unforeseen clues, keep `private/` local and inspect visible text before publishing external runs.
