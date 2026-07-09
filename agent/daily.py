"""The daily sitrep run — the only place a model wakes (PRD §3, decisions
#17–19).

    uv run agent/daily.py --replay tests/fixtures/morning-1 --assess recorded
    uv run agent/daily.py                     # live fetch + live model

Flow: deterministic cycle (``pipeline.runner.run_cycle``) → abort check
(PRD §7: both real-time feeds down means the report would be blind — worse
than no report) → gate verdict → model assessment **only if CHANGED** →
deterministic render. The all-quiet morning renders without waking the
model; a degraded morning publishes with the banner. One exception:
skills/news-summary/SKILL.md runs every day regardless of verdict, via a
second, narrower model call (``assessor.search_news``) — a quiet morning
by the feeds' own thresholds can still be the morning a story breaks that
none of them have caught.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT))

import health  # noqa: E402
from pipeline import render, runner, store  # noqa: E402

from agent import assess  # noqa: E402


class Abort(RuntimeError):
    """No sitrep exists this morning — this is an alert, not a page."""


def _write_backup(sitrep_path: Path, run_at: str, run_number: int) -> Path:
    """A timestamped copy alongside the live sitrep. ``out/``/``reports/``
    are gitignored and rebuilt every run (CLAUDE.md) — this isn't an audit
    trail (``data/`` already is one); it just keeps a specific run's page
    from being overwritten in place by the next one. ``run_at`` only has
    second precision (``pipeline.runner``), so two cycles inside the same
    second are possible (fast replays, the 15-min loop catching up after a
    gap) — ``run_number`` keeps their backups from colliding."""
    tag = datetime.fromisoformat(run_at).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = sitrep_path.parent / "history"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{sitrep_path.stem}-{tag}-run{run_number}{sitrep_path.suffix}"
    backup_path.write_bytes(sitrep_path.read_bytes())
    return backup_path


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

    # skills/news-summary/SKILL.md runs every day, independent of the
    # sitrep gate above: a quiet morning by GDACS/USGS/ReliefWeb's own
    # thresholds can still be the morning a fast-moving story breaks that
    # none of those feeds have caught. When the gate above already woke
    # the model, its own news_items cover the day — no second call.
    if assessment is not None:
        store.save_news(
            data_dir,
            manifest["run_at"],
            assessment["news_items"],
            searched=assessment.get("searched"),
        )
    elif assessor is not None and hasattr(assessor, "search_news"):
        news_context = assess.build_context(cycle)
        result = assessor.search_news(news_context)
        items = assess.validate_news_items(result.get("items") or [], news_context)
        store.save_news(data_dir, manifest["run_at"], items, searched=result.get("searched"))
    news = store.load_news(data_dir)

    sitrep_path = render.write_sitrep(
        cycle["store"], manifest, out_path, assessment, cycle["candidates"], news
    )
    _write_backup(sitrep_path, manifest["run_at"], manifest["run_number"])
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
        _emit_github_output("QUIET", "abort")
        raise SystemExit(health.ABORT_EXIT_CODE)

    print(f"sitrep: {args.out} · store: {args.data_dir}")

    verdict = health.evaluate(manifest)
    print(f"health: {verdict['status']}")
    _emit_github_output(manifest["verdict"], verdict["status"])
    print(manifest["verdict"])  # docstring contract: the final line is the verdict


def _emit_github_output(verdict: str, status: str) -> None:
    """Machine-readable signal for the sitrep workflow (PRD §13 outputs)."""
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as fh:
            fh.write(f"verdict={verdict}\n")
            fh.write(f"health={status}\n")


if __name__ == "__main__":
    main()
