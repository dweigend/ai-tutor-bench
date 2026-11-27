"""Revision manifests for export and reporting, outside the dispatch path."""

from pathlib import Path

from ..contracts import ROOT, Contract
from .primitives import Sha256
from .revisions import execution_revision, file_revision

EXPORT_FILES = (
    "runtime/core/export_manifest.py",
    "runtime/core/export_receipt.py",
    "runtime/core/publish.py",
    "runtime/store.py",
    "runtime/v5/export.py",
    "runtime/v5/replay.py",
    "runtime/v5/workflow.py",
)
ANALYSIS_FILES = (
    "analyse/__init__.py",
    "analyse/bestand.py",
    "analyse/detektoren-v1.json",
    "analyse/detektoren.py",
    "v5/drift/bewertung.py",
    "v5/schema/rubric.json",
    "v5/schema/signal-modus-schema.json",
    "v5/schema/signal_modus.py",
)


class Revisions(Contract):
    execution_revision: Sha256
    export_revision: Sha256
    analysis_revision: Sha256


def export_revision(root: Path) -> str:
    return file_revision(root, "export", EXPORT_FILES)


def check_revisions(root: Path = ROOT, assets: tuple[str, ...] = ()) -> Revisions:
    return Revisions(
        execution_revision=execution_revision(root, assets),
        export_revision=export_revision(root),
        analysis_revision=file_revision(root, "analysis", ANALYSIS_FILES),
    )
