"""Test the installed command and the boundary between local and shareable data."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from shutil import copytree
from typing import ClassVar, Literal

import pytest

from ai_tutor_bench.runtime.contracts import ROOT, canonical, digest
from ai_tutor_bench.runtime.core.cell_plan import PlannedCell
from ai_tutor_bench.runtime.core.export_receipt import PublicReceipt
from ai_tutor_bench.runtime.core.freeze import MANIFEST, PUBLIC_ASSETS, check_freeze
from ai_tutor_bench.runtime.core.result_settlement import AttemptResult, CellOutcome, SettledAttempt
from ai_tutor_bench.runtime.core.start_journal import StartEvent
from ai_tutor_bench.runtime.v5.adapters.alternate import AlternateAdapter
from ai_tutor_bench.runtime.v5.contracts import AdapterProtocol, EpisodeHistory
from ai_tutor_bench.runtime.v5.export import BLIND_FILE, BLIND_SIDECAR, RAW_FILE
from ai_tutor_bench.runtime.v5.fixture import FixtureAdapter, fixture_spec
from ai_tutor_bench.runtime.v5.replay import replay_private, replay_public
from ai_tutor_bench.runtime.v5.runner import RUN_FILE, START_FILE
from ai_tutor_bench.runtime.v5.suite import load_suite
from ai_tutor_bench.runtime.v5.workflow import PRIVATE_EXPORT_DIR, run_benchmark

EXPECTED = 161
PRIVATE_IDENTITY = "identity-Zenith-Fable"
PRIVATE_PATH = "/srv/synthetic-vault/unlisted.record"
RAW_SENTINEL = "raw-payload-Copper-Vela"
LOCAL_PATHS = (
    PRIVATE_PATH,
    r"\\synthetic-server\share\folder\unlisted.record",
    "//synthetic-server/share/folder/unlisted.record",
    "/secret.txt",
    "path:/secret.txt",
    "/etc/passwd",
    "/var/data",
    "/tmp/session",
    "/root",
    r"C:\vault\unlisted.record",
    "file:///secret.txt",
)
BUNDLED_IDENTITIES = (
    FixtureAdapter.identity,
    AlternateAdapter.identity.upper(),
    "offline-drift-learner:" + "a" * 64,
    "offline-drift-tutor:" + "b" * 64,
)
ALLOWED_PROSE = "Vergleiche 1/2 mit a/b. Quelle: https://example.org/task."


def cli(cwd: Path, *args: str, fail: bool = False) -> subprocess.CompletedProcess[str]:
    command = Path(sys.executable).with_name("ai-tutor-bench")
    completed = subprocess.run(
        [str(command), *args],
        cwd=cwd,
        env={"PATH": str(command.parent), "LANG": "C.UTF-8"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == (1 if fail else 0), completed.stderr
    return completed


def jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def replay_args(run: Path) -> tuple[str, ...]:
    return ("replay", "--public-dir", str(run / "public"))


def test_both_adapters_start_in_an_empty_directory(tmp_path: Path) -> None:
    assert list(tmp_path.iterdir()) == []
    freeze = json.loads(cli(tmp_path, "check-freeze").stdout)
    assert len(freeze["freeze_sha256"]) == 64
    revisions = json.loads(cli(tmp_path, "check-revisions").stdout)
    assert set(revisions) == {"execution_revision", "export_revision", "analysis_revision"}
    assert len(set(revisions.values())) == 3
    replies = {}
    run_ids = {}
    plans = {}
    for name in ("fixture", "alternate"):
        run = tmp_path / name
        summary = json.loads(
            cli(tmp_path, "dry-run", "--adapter", name, "--output-dir", str(run)).stdout
        )
        assert summary["adapter"] == name
        assert summary["row_count"] == EXPECTED
        assert summary["cost_microusd"] == 0
        public = run / "public"
        assert {path.name for path in public.iterdir()} == {BLIND_FILE, BLIND_SIDECAR}
        sidecar = json.loads((public / BLIND_SIDECAR).read_bytes())
        assert set(sidecar) == {"file_sha256", "row_count"}
        assert (
            sidecar["file_sha256"] == hashlib.sha256((public / BLIND_FILE).read_bytes()).hexdigest()
        )
        rows = jsonl(public / BLIND_FILE)
        assert all(set(row) == {"blind_id", "text"} for row in rows)
        replies[name] = Counter(row["text"] for row in rows)

        raw = jsonl(run / "private" / PRIVATE_EXPORT_DIR / RAW_FILE)
        private = json.loads((run / "private" / "run.json").read_bytes())
        plan = private["spec"]["plan"]
        assert private["execution_revision"] == revisions["execution_revision"]
        assert plan["freeze_sha256"] == freeze["freeze_sha256"]
        assert all(cell["key"]["seed"] == 0 for cell in plan["cells"])
        run_ids[name] = plan["run_id"]
        plans[name] = [
            {k: v for k, v in cell["key"].items() if k != "run_id"} for cell in plan["cells"]
        ]
        assert {row["blind_id"] for row in raw} == {row["blind_id"] for row in rows}

        result = json.loads(
            cli(
                tmp_path,
                *replay_args(run),
                "--adapter",
                name,
                "--private-dir",
                str(run / "private"),
            ).stdout
        )
        assert result["planned"] == result["visible"] == EXPECTED
        assert result["without_visible_text"] == 0
        assert result["outcomes"]["ok"] == EXPECTED
        assert result["cost_microusd"] == 0

    assert replies["fixture"] != replies["alternate"]
    assert run_ids["fixture"] != run_ids["alternate"]
    assert plans["fixture"] == plans["alternate"]


@pytest.mark.parametrize(
    "change", ["tamper", "forged-manifest", "missing", "symlink", "directory-link", "extra"]
)
def test_freeze_rejects_asset_changes(tmp_path: Path, change: str) -> None:
    assets = tmp_path / "assets"
    copytree(ROOT, assets, ignore=lambda _path, names: {"__pycache__"} & set(names))
    target = assets / PUBLIC_ASSETS[0]
    cli(tmp_path, "check-freeze", "--asset-root", str(assets))
    if change == "tamper":
        target.write_bytes(target.read_bytes() + b"\n")
    elif change == "forged-manifest":
        target.write_bytes(target.read_bytes() + b"\n")
        manifest = assets / MANIFEST
        assets_map = json.loads(manifest.read_bytes())
        assets_map[PUBLIC_ASSETS[0]] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(assets_map))
    elif change == "missing":
        target.unlink()
    elif change == "symlink":
        target.unlink()
        target.symlink_to(ROOT / PUBLIC_ASSETS[0])
    elif change == "directory-link":
        other = tmp_path / "relocated"
        target.parent.rename(other)
        target.parent.symlink_to(other, target_is_directory=True)
    else:
        target.with_name("surprise.txt").write_text("unlisted")
    failure = cli(tmp_path, "check-freeze", "--asset-root", str(assets), fail=True)
    assert failure.stderr == "check-freeze failed: ValueError\n"


def test_cli_pause_resume_and_idempotent_replay(tmp_path: Path) -> None:
    run = tmp_path / "run"
    args = ("dry-run", "--adapter", "alternate", "--output-dir", str(run))
    assert json.loads(cli(tmp_path, *args, "--stop-after", "11").stdout)["state"] == "paused"
    journal = run / "private" / START_FILE
    prior = journal.read_bytes()
    assert len(prior.splitlines()) == 11
    assert not (run / "public").exists()
    initial = json.loads(cli(tmp_path, *args).stdout)
    after = journal.read_bytes()
    assert after.startswith(prior)
    keys = [json.dumps(row["key"], sort_keys=True) for row in jsonl(journal)]
    assert len(keys) == len(set(keys)) == EXPECTED
    assert json.loads(cli(tmp_path, *args).stdout) == initial
    report = json.loads(cli(tmp_path, *replay_args(run)).stdout)
    assert report["planned"] == EXPECTED
    assert journal.read_bytes() == after


@pytest.mark.parametrize("change", ["payload", "forged-row-count", "extra-file"])
def test_replay_rejects_corrupted_release(tmp_path: Path, change: str) -> None:
    run = tmp_path / "run"
    cli(tmp_path, "dry-run", "--output-dir", str(run))
    public = run / "public"
    blind = public / BLIND_FILE
    if change == "extra-file":
        (public / "receipt.json").write_text("{}")
    else:
        data = b"".join(blind.read_bytes().splitlines(keepends=True)[:-1])
        blind.write_bytes(data)
        if change == "forged-row-count":
            (public / BLIND_SIDECAR).write_text(
                json.dumps(
                    {
                        "file_sha256": hashlib.sha256(data).hexdigest(),
                        "row_count": EXPECTED - 1,
                    }
                )
            )
    result = cli(tmp_path, *replay_args(run), fail=True)
    assert result.stderr == "replay failed: ValueError\n"


@pytest.mark.parametrize(
    ("missing", "error_type"), [(False, "ValidationError"), (True, "FileNotFoundError")]
)
def test_cli_replay_errors_do_not_disclose_input_or_path(
    tmp_path: Path, missing: bool, error_type: str
) -> None:
    run = tmp_path / "run"
    cli(tmp_path, "dry-run", "--output-dir", str(run))
    private = tmp_path / "private-path-Orchid-Vega"
    (run / "private").rename(private)
    marker = "invalid-revision-Saffron-Lyra"
    if missing:
        (private / RUN_FILE).unlink()
    else:
        bound_run = json.loads((private / RUN_FILE).read_bytes())
        bound_run["execution_revision"] = marker
        (private / RUN_FILE).write_text(json.dumps(bound_run))
    result = cli(tmp_path, *replay_args(run), "--private-dir", str(private), fail=True)
    assert result.returncode != 0
    assert result.stderr == f"replay failed: {error_type}\n"
    for secret in (marker, private.name, str(private / RUN_FILE)):
        assert secret not in result.stdout
        assert secret not in result.stderr


class SentinelAdapter:
    kind: ClassVar[Literal["fixture"]] = "fixture"
    identity: ClassVar[str] = PRIVATE_IDENTITY

    def __init__(self, wrapped: AdapterProtocol, visible: str | None = None) -> None:
        self.wrapped = wrapped
        self.visible = visible

    def reserve(self, cell: PlannedCell) -> int:
        return self.wrapped.reserve(cell)

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        baseline = self.wrapped.execute(cell, start, history)
        raw = {"path": PRIVATE_PATH, "identity": PRIVATE_IDENTITY, "payload": RAW_SENTINEL}
        if self.visible is not None:
            result = AttemptResult(
                key=start.key,
                outcome=CellOutcome.OK,
                visible_text=self.visible,
                finish_reason="stop",
                raw=raw,
            )
        elif cell.key.suite == "drift" and cell.key.turn == 1 and not history:
            result = AttemptResult(
                key=start.key,
                outcome=CellOutcome.TECHNICAL,
                visible_text=None,
                finish_reason=None,
                raw=raw,
            )
        else:
            result = baseline.result.model_copy(update={"raw": raw})
        return SettledAttempt(result=result, billing=baseline.billing)


def test_private_outcomes_recompute_and_blind_payload_excludes_sentinels(tmp_path: Path) -> None:
    spec, adapters = load_suite(check_freeze(), "fixture")
    role = ("offline", "learner")
    adapters[role] = SentinelAdapter(adapters[role])
    private = tmp_path / "private"
    public = tmp_path / "public"
    run_benchmark(spec, adapters, private, public)
    raw = (private / PRIVATE_EXPORT_DIR / RAW_FILE).read_bytes()
    released = b"".join(path.read_bytes() for path in public.iterdir())
    for sentinel in (PRIVATE_IDENTITY, PRIVATE_PATH, RAW_SENTINEL):
        assert sentinel.encode() in raw
        assert sentinel.encode() not in released
    for marker in (b'"attempts"', b'"model"', b'"cell_id"', b'"execution_revision"'):
        assert marker in raw
        assert marker not in released
    counts = Counter(row["status"] for row in jsonl(private / PRIVATE_EXPORT_DIR / RAW_FILE))
    assert counts == {"ok": 33, "technisch": 2, "zensiert": 126}
    report = json.loads(cli(tmp_path, *replay_args(tmp_path), "--private-dir", str(private)).stdout)
    assert report["planned"] == sum(counts.values()) == EXPECTED
    assert report["visible"] == counts["ok"]
    assert report["without_visible_text"] == counts["technisch"] + counts["zensiert"]
    assert {key: value for key, value in report["outcomes"].items() if value} == counts
    assert report["cost_microusd"] == 0


@pytest.mark.parametrize("visible", (PRIVATE_IDENTITY, *LOCAL_PATHS, *BUNDLED_IDENTITIES))
def test_publication_blocks_identity_or_path_in_visible_text(tmp_path: Path, visible: str) -> None:
    with pytest.raises(ValueError, match="identifier|local path"):
        run_benchmark(
            fixture_spec(),
            {("offline", "tutor"): SentinelAdapter(FixtureAdapter(), f"Text: {visible} Ende")},
            tmp_path / "private",
            tmp_path / "public",
        )
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("visible", (*LOCAL_PATHS, *BUNDLED_IDENTITIES))
def test_public_replay_blocks_identity_or_path_in_visible_text(
    tmp_path: Path, visible: str
) -> None:
    data = canonical({"blind_id": "7" * 32, "text": f"Text: {visible} Ende"}) + b"\n"
    (tmp_path / BLIND_FILE).write_bytes(data)
    receipt = PublicReceipt(file_sha256=digest(data), row_count=1)
    (tmp_path / BLIND_SIDECAR).write_text(receipt.model_dump_json())
    with pytest.raises(ValueError, match="identifier|local path"):
        replay_public(tmp_path, expected=1)


def test_publication_and_replay_allow_fraction_and_prose(tmp_path: Path) -> None:
    spec = fixture_spec()
    public = tmp_path / "public"
    receipt = run_benchmark(
        spec,
        {("offline", "tutor"): SentinelAdapter(FixtureAdapter(), ALLOWED_PROSE)},
        tmp_path / "private",
        public,
    )
    assert {row["text"] for row in jsonl(public / BLIND_FILE)} == {ALLOWED_PROSE}
    assert replay_public(public, spec.plan.expected_cell_count) == (
        receipt.public,
        spec.plan.expected_cell_count,
    )


def test_custom_adapter_identity_requires_private_replay_context(tmp_path: Path) -> None:
    spec, adapters = load_suite(check_freeze(), "fixture")
    role = ("offline", "tutor")
    adapters[role] = SentinelAdapter(adapters[role], PRIVATE_IDENTITY)
    private = tmp_path / "private"
    public = tmp_path / "public"
    with pytest.raises(ValueError, match="private identifier"):
        run_benchmark(spec, adapters, private, public)
    assert not public.exists()

    # Simulate a manually shared bundle with valid matching hashes.
    public.mkdir()
    for name in (BLIND_FILE, BLIND_SIDECAR):
        (public / name).write_bytes((private / PRIVATE_EXPORT_DIR / name).read_bytes())
    receipt, visible = replay_public(public, EXPECTED)
    assert visible == EXPECTED
    with pytest.raises(ValueError, match="private identifier"):
        replay_private(private, public, spec.plan, receipt)
    result = cli(tmp_path, *replay_args(tmp_path), "--private-dir", str(private), fail=True)
    assert result.stderr == "replay failed: ValueError\n"
    assert PRIVATE_IDENTITY not in result.stdout + result.stderr
