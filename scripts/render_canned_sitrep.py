"""Model-free sitrep pages — the §13.6 stand-ins for the model step.

Two modes, both deterministic (this imports the write_dashboard *template
function*; it never calls a model):
- --mode quiet   : the explicit "all quiet" page with a feed-health line
- --mode canned  : renders tests/fixtures/assessment/ over the store, so
                   the sitrep workflow runs end-to-end without an API key
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # noqa: E402 — scripts/ is not a package
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import health  # noqa: E402
from agent.tools import write_dashboard  # noqa: E402
from report_date import report_date  # noqa: E402


def degraded_note(verdict: dict) -> str | None:
    if verdict["status"] == "ok":
        return None
    return "Degraded coverage this morning: " + "; ".join(verdict["blind_hazards"]) + "."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["quiet", "canned"], required=True)
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data")
    parser.add_argument(
        "--assessment",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "assessment" / "assessment.json",
    )
    parser.add_argument("--now", type=datetime.fromisoformat, default=None)
    args = parser.parse_args(argv)

    now = args.now or datetime.now(timezone.utc)
    manifest = json.loads((args.data / "manifest.json").read_text())
    verdict = health.evaluate(manifest, now)
    date = report_date(now).isoformat()
    feeds_line = "; ".join(
        f"{name.upper()} last success {feed.get('last_success_utc') or 'never'} ({verdict['feed_states'][name]})"
        for name, feed in manifest["feeds"].items()
    )
    blind = "Tsunami warnings (NOAA) and ReliefWeb-confirmed impacts are not visible."
    if note := degraded_note(verdict):
        blind = f"{note} {blind}"

    if args.mode == "quiet":
        print(
            write_dashboard(
                title="All quiet",
                summary=(
                    "Nothing cleared the reporting bar since the previous report: "
                    "no new Orange or Red alerts and no significant earthquakes. "
                    f"The pipeline ran and found nothing. Feed health: {feeds_line}."
                ),
                events=[],
                blindspots=blind,
                report_date=date,
            )
        )
        return 0

    assessment = json.loads(args.assessment.read_text())
    events = []
    for path in sorted((args.data / "events").glob("*.json")):
        ev = json.loads(path.read_text())
        note = assessment.get("events", {}).get(ev["id"], {}).get("note_md")
        impact = "; ".join(
            f"{i['metric']}: {i['value']} ({i['label'].title()}, {i['source']})"
            for i in ev.get("impact", [])
        )
        merge = ev.get("merge", {})
        events.append(
            {
                "name": ev.get("geo", {}).get("place_name") or ev["id"],
                "hazard": ev["hazard"],
                "alert_level": ev.get("severity", {}).get("gdacs_alertlevel") or "Green",
                "location": ev.get("geo", {}).get("country_iso3") or "",
                "time_utc": ev.get("times", {}).get("origin_utc") or "",
                "impact": impact,
                "change_note": note or ev.get("change", {}).get("summary", ""),
                "sources": ", ".join(s["feed"] for s in ev.get("sources", [])),
                "merge_confidence": merge.get("confidence", ""),
                "anchor": (ev.get("identity", {}).get("usgs_ids") or [None])[0]
                or str(ev.get("identity", {}).get("gdacs_event_id") or ev["id"]),
            }
        )
    print(
        write_dashboard(
            title=f"Morning situation report — {date}",
            summary=assessment["summary_md"],
            events=events,
            blindspots=blind,
            report_date=date,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
