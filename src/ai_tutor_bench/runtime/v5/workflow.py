"""Connect v5 dispatch and publication without including export in its revision."""

from collections.abc import Mapping
from pathlib import Path

from ..contracts import ROOT
from ..core.export_receipt import ExportReceipt
from ..core.projection_revisions import export_revision
from .contracts import AdapterKey, AdapterProtocol, V5RunSpec
from .export import publish_run
from .runner import execute_run

PRIVATE_EXPORT_DIR = "export"


def run_benchmark(
    spec: V5RunSpec,
    adapters: Mapping[AdapterKey, AdapterProtocol],
    private: Path,
    public: Path,
    *,
    root: Path = ROOT,
    stop_after: int | None = None,
) -> ExportReceipt:
    private = private.parent.resolve() / private.name
    public = public.parent.resolve() / public.name
    if public.is_relative_to(private) or private.is_relative_to(public):
        raise ValueError("public and private run directories must be separate")
    if public.is_symlink() or not public.parent.is_dir():
        raise ValueError("public export needs an existing parent and a regular destination")
    target = private / PRIVATE_EXPORT_DIR
    if public.exists() and not target.exists():
        raise FileExistsError(public)
    with execute_run(spec, adapters, private, root=root, stop_after=stop_after) as snapshot:
        revision = None if target.exists() else export_revision(root)
        return publish_run(target, public, snapshot, revision)
