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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.runner import run_once  # noqa: E402


def main() -> None:
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
    print(manifest["verdict"])


if __name__ == "__main__":
    main()
