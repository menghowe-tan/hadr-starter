"""The daily sitrep run — the only place a model wakes (PRD §3, decisions
#17–19).

    uv run agent/daily.py --replay tests/fixtures/morning-1 --assess recorded
    uv run agent/daily.py                     # live fetch + live model

Flow: deterministic cycle (``pipeline.runner.run_cycle``) → abort check
(PRD §7: both real-time feeds down means the report would be blind — worse
than no report) → gate verdict → model assessment **only if CHANGED** →
deterministic render. The all-quiet morning renders without waking the
model; a degraded morning publishes with the banner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT))

from pipeline import render, runner  # noqa: E402

from agent import assess  # noqa: E402


class Abort(RuntimeError):
    """No sitrep exists this morning — this is an alert, not a page."""


def run_daily(replay_dir, data_dir, out_path, assessor) -> dict:
    """One daily sitrep run; returns the manifest. Raises ``Abort`` when
    both real-time feeds are down (design §3 state 4: the previous sitrep
    stays live; alert copy says what broke)."""
    cycle = runner.run_cycle(replay_dir, data_dir)
    manifest = cycle["manifest"]
    feeds = manifest["feeds"]

    if feeds["gdacs"]["status"] != "ok" and feeds["usgs"]["status"] != "ok":
        raise Abort(
            "ABORT: GDACS and USGS are both unreachable — this morning would be "
            "blind, and missing data is worse than no report (PRD §7). "
            f"Last good GDACS fetch: {feeds['gdacs'].get('fetched_at') or 'never'}; "
            f"last good USGS fetch: {feeds['usgs'].get('fetched_at') or 'never'}. "
            "No sitrep published; the previous sitrep stays live at its URL."
        )

    assessment = None
    if manifest["verdict"] == "CHANGED" and assessor is not None:
        context = assess.build_context(cycle)
        assessment = assess.validate_assessment(assessor(context), context)

    render.write_sitrep(
        cycle["store"], manifest, out_path, assessment, cycle["candidates"]
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, default=None, metavar="FIXTURE_DIR")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("reports/sitrep.html"))
    parser.add_argument(
        "--assess",
        choices=["live", "recorded", "off"],
        default="live",
        help="'recorded' replays <replay-dir>/assessment.json; 'off' renders "
        "without model prose (deterministic fallback summary)",
    )
    args = parser.parse_args()

    if args.assess == "live":
        assessor = assess.ClaudeAssessor()
    elif args.assess == "recorded":
        if args.replay is None:
            parser.error("--assess recorded needs --replay (reads assessment.json there)")
        assessor = assess.RecordedAssessor(Path(args.replay) / "assessment.json")
    else:
        assessor = None

    try:
        manifest = run_daily(args.replay, args.data_dir, args.out, assessor)
    except Abort as abort:
        print(abort, file=sys.stderr)
        raise SystemExit(2)

    print(f"sitrep: {args.out} · store: {args.data_dir}")
    print(manifest["verdict"])


if __name__ == "__main__":
    main()
