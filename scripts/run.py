"""Run one fetch cycle of the HADR pipeline.

    uv run scripts/run.py --replay tests/fixtures/eventful
    uv run scripts/run.py                 # live: one polite fetch per feed

Prints a short account of the run and, on the final line, the verdict:
``CHANGED`` or ``QUIET``. Writes canonical events + run manifest under
``data/`` and the dashboard skeleton to ``reports/dashboard.html``
(gitignored — generated views are never committed).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import health  # noqa: E402
from pipeline.runner import run_once  # noqa: E402


def _emit_github_output(verdict: str, status: str) -> None:
    """Machine-readable signal for the monitor workflow (PRD §13 outputs)."""
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as fh:
            fh.write(f"verdict={verdict}\n")
            fh.write(f"health={status}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay",
        type=Path,
        default=None,
        metavar="FIXTURE_DIR",
        help="replay from a fixture directory instead of fetching live",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("reports/dashboard.html"))
    args = parser.parse_args()

    manifest = run_once(args.replay, args.data_dir, args.out)

    for feed, info in manifest["feeds"].items():
        print(
            f"{feed}: {info['count_fetched']} records fetched, "
            f"{info['count_gated']} past the gate"
        )
    changes = manifest["changes"]
    if changes:
        summary = ", ".join(f"{c['change']} {c['event_id']}" for c in changes)
        print(f"changes ({len(changes)}): {summary}")
    else:
        print("changes: none")
    print(f"store: {args.data_dir} · page: {args.out}")

    verdict = health.evaluate(manifest)
    print(f"health: {verdict['status']}")
    _emit_github_output(manifest["verdict"], verdict["status"])
    print(manifest["verdict"])  # docstring contract: the final line is the verdict
    return health.ABORT_EXIT_CODE if verdict["status"] == "abort" else 0


if __name__ == "__main__":
    sys.exit(main())
