"""Verify and execute the public suite from an installed package."""

import argparse
import json
import sqlite3
from pathlib import Path

from ..core.freeze import check_freeze
from ..core.projection_revisions import check_revisions
from .replay import replay_private, replay_public
from .runner import RunPaused
from .suite import SUITE_ASSETS, load_suite
from .workflow import run_benchmark


def commands() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Tutor Bench v5")
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("check-freeze", help="Verify the complete public asset inventory")
    freeze.add_argument("--asset-root", type=Path, help="Verify a copy of the package asset tree")
    sub.add_parser("check-revisions", help="Print execution, export and analysis hashes")
    dry = sub.add_parser("dry-run", help="Run or resume the offline suite")
    dry.add_argument("--adapter", choices=("fixture", "alternate"), default="fixture")
    dry.add_argument("--output-dir", type=Path, required=True)
    dry.add_argument("--stop-after", type=int, help="Pause after this many new attempts")
    replay = sub.add_parser("replay", help="Verify a blind export without dispatch")
    replay.add_argument("--adapter", choices=("fixture", "alternate"), default="fixture")
    replay.add_argument("--public-dir", type=Path, required=True)
    replay.add_argument("--private-dir", type=Path, help="Also verify and aggregate local raw rows")
    return parser


def execute(args: argparse.Namespace) -> object:
    if args.command == "check-freeze":
        freeze = check_freeze(args.asset_root) if args.asset_root is not None else check_freeze()
        return {"freeze_sha256": freeze}
    freeze = check_freeze()
    if args.command == "check-revisions":
        return check_revisions(assets=SUITE_ASSETS).model_dump(mode="json")
    spec, adapters = load_suite(freeze, args.adapter)
    if args.command == "replay":
        expected = spec.plan.expected_cell_count
        receipt, visible = replay_public(args.public_dir, expected)
        report: dict[str, object] = {
            "file_sha256": receipt.file_sha256,
            "planned": expected,
            "visible": visible,
            "without_visible_text": expected - visible,
        }
        if args.private_dir is not None:
            report.update(replay_private(args.private_dir, args.public_dir, spec.plan, receipt))
        return report
    if args.stop_after is not None and args.stop_after < 1:
        raise ValueError("--stop-after must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        receipt = run_benchmark(
            spec,
            adapters,
            args.output_dir / "private",
            args.output_dir / "public",
            stop_after=args.stop_after,
        )
    except RunPaused:
        return {"state": "paused", "adapter": args.adapter}
    return {"adapter": args.adapter, "cost_microusd": 0, **receipt.public.model_dump(mode="json")}


def main() -> None:
    parser = commands()
    args = parser.parse_args()
    try:
        report = execute(args)
    except (ValueError, OSError, RuntimeError, LookupError, TypeError, sqlite3.Error) as error:
        parser.exit(1, f"{args.command} failed: {type(error).__name__}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
