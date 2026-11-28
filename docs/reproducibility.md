# Reproducibility, Adapter Contract, and Failure States (`ai-tutor-bench` v5)

This guide documents the operational guarantees behind `ai-tutor-bench` (`0.1.0`, Suite `v5`): connecting a custom tutor adapter, independent revision digests, pause/resume journaling, private-to-public reconciliation, cell censoring states, and blind-projection boundaries.

## Connecting a custom tutor adapter

Custom models plug into the frozen `v5` execution pipeline by implementing `AdapterProtocol` from [`ai_tutor_bench.runtime.v5.contracts`](../src/ai_tutor_bench/runtime/v5/contracts.py), binding it into the `load_suite(...)` adapter map, and invoking `run_benchmark(...)` from [`ai_tutor_bench.runtime.v5.workflow`](../src/ai_tutor_bench/runtime/v5/workflow.py):

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

`AdapterBinding` validates `kind` against five supported literals in `ai_tutor_bench.runtime.core.start_journal.AdapterKind`: `"fixture"`, `"openrouter"`, `"simulator-cli"`, `"vllm"`, and `"peft"`. In the `v5` offline suite (`161` total cells), replacing `(OFFLINE_ARM, TUTOR_ROLE)` routes the **97 tutor cells** to your adapter while the **64 scripted learner cells** remain handled by the built-in offline learner adapter.

The complete offline example below runs as-is on a clean checkout of `ai-tutor-bench 0.1.0`:

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

`reserve()` runs before dispatch so budget caps can censor remaining cells cleanly. `execute()` must return billing evidence even when a provider call fails; an unhandled exception leaves the start entry unsettled for safe resume. For live providers, swap `kind` to `"openrouter"`, `"vllm"`, `"peft"`, or `"simulator-cli"`, set a positive `AbortPolicy.budget_microusd` on `spec`, and report actual provider cost in `BillingReport`.

## Three independent revision digests

`uv run --locked ai-tutor-bench check-revisions` computes three separate SHA-256 digests so changes to downstream analysis code never invalidate sealed runs or blind exports:

- **`execution_revision`:** Suite construction, adapters, and execution assets on the dispatch path.
- **`export_revision`:** Raw-row validation, blind projection, receipt sealing, and replay verification.
- **`analysis_revision`:** Rubric schema, signal-mode matrix, drift scoring, and deterministic surface detectors (`detektoren-v1.json`).

Record all three digests alongside the Git commit SHA, `freeze_sha256`, adapter identity, and `seed` whenever you publish results.

## Pause, resume, and private reconciliation

Every cell attempt is appended to a start journal before dispatch. If a run stops early (or you test interruption with `--stop-after`), re-running with the same `--output-dir` resumes deterministically without re-dispatching settled cells:

```sh
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/resume-check --stop-after 11
uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/resume-check
```

After running `uv run --locked ai-tutor-bench dry-run --adapter alternate --output-dir runs/alternate` (from the [README Quick Start](../README.md#quick-start-offline-0)), reconcile the public blind export against its sealed local `private/` directory (`private/export/raw.jsonl` and `private/export/receipt.json`):

```sh
uv run --locked ai-tutor-bench replay \
  --adapter alternate \
  --public-dir runs/alternate/public \
  --private-dir runs/alternate/private
```

## Planned vs. observed denominators and the seven cell states

Public replay checks the sidecar SHA-256 manifest, canonical JSON formatting, unique 32-hex `blind_id` tokens, and exact row count (`161`), reporting `planned`, `visible`, and `without_visible_text`.

Adding `--private-dir` breaks down all seven cell outcomes:

| State | Meaning | Emits visible text in `public/blind.jsonl`? |
|---|---|---|
| `ok` | Completed cleanly with verified adapter identity | Yes |
| `abgeschnitten` | Truncated response with verified adapter identity | Yes |
| `leer` | Empty model output | No (`text: null`) |
| `technisch` | Technical or transport failure | No (`text: null`) |
| `abgebrochen` | Started in journal without settled completion | No (`text: null`) |
| `zensiert` | Remaining episode or run cells censored after an upstream failure, budget cap, or subscription limit | No (`text: null`) |
| `nicht_gestartet` | Never started | No (`text: null`) |

Because failed and censored cells remain as `text: null` rows, every reported rate stays anchored to the full planned denominator.

## Blind-projection boundaries

`public/` contains only lexicographically sorted `{"blind_id", "text"}` rows in `blind.jsonl` plus `blind.jsonl.manifest.json`. Lexicographic sorting prevents file order from exposing arm or scenario sequence, and fresh `blind_id` tokens are generated at seal time.

Raw payloads, model identities, `run_id`, `cell_id`, episode hashes, attempt logs, and receipts stay in `private/`. Export and replay reject visible text that matches local filesystem path patterns or bundled adapter identifiers; with `--private-dir`, replay also checks bound custom model IDs and run/cell/episode tokens. Any `identity_violation` blocks publication. Because open-ended text can still contain unforeseen identifying clues, keep `private/` local and inspect visible text before publishing external runs.
