"""Execution revision from explicit source and frozen input lists."""

from pathlib import Path

from ..contracts import canonical, digest

EXECUTION_FILES = (
    "runtime/__init__.py",
    "runtime/contracts.py",
    "runtime/core/__init__.py",
    "runtime/core/cell_plan.py",
    "runtime/core/primitives.py",
    "runtime/core/result_settlement.py",
    "runtime/core/revisions.py",
    "runtime/core/run_summary.py",
    "runtime/core/settlement.py",
    "runtime/core/start_journal.py",
    "runtime/v5/__init__.py",
    "runtime/v5/contracts.py",
    "runtime/v5/runner.py",
)
EXECUTION_ASSET_ROOTS = (
    "runtime/v5/adapters/",
    "v5/szenarien/",
    "v5/drift/",
    "v5/schema/",
)
EXECUTION_ENTRY_ASSETS = (
    "runtime/core/freeze.py",
    "v5/__init__.py",
    "runtime/v5/fixture.py",
    "runtime/v5/fixture-references.json",
    "runtime/v5/suite.py",
)
FIXTURE_SOURCE = "runtime/v5/fixture.py"


def file_revision(root: Path, domain: str, files: tuple[str, ...]) -> str:
    root = root.resolve()
    entries = []
    for name in sorted(files):
        path = (root / name).resolve()
        if not path.is_relative_to(root) or path.relative_to(root).as_posix() != name:
            raise ValueError(f"revision path must be canonical and benchmark-relative: {name}")
        entries.append((name, digest(path.read_bytes())))
    return digest(canonical([domain, entries]))


def execution_revision(root: Path, assets: tuple[str, ...] = ()) -> str:
    if len(set(assets)) != len(assets):
        raise ValueError("duplicate execution asset")
    for name in assets:
        if name not in EXECUTION_ENTRY_ASSETS and not name.startswith(EXECUTION_ASSET_ROOTS):
            raise ValueError(f"file is outside the additional execution assets: {name}")
    return file_revision(root, "execution", EXECUTION_FILES + assets)
