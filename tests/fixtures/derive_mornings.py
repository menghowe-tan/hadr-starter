"""Derive the two consecutive-morning fixtures from the real eventful capture.

    uv run tests/fixtures/derive_mornings.py

``morning-2/`` is the 2025-03-28 capture **verbatim** (the real final state:
Mandalay Red both feeds, PAGER red). ``morning-1/`` is an *earlier snapshot
of the same morning*, cut at 06:30 UTC — after the M 7.7 mainshock
(06:20 UTC) but before the M 6.7 aftershock (06:32 UTC) — with the evolving
records rolled back to plausible first-report states. Every edit is explicit
below; everything else is the capture unmodified. The edits are documented
as a deviation in ``implementation-notes.md`` (the GDACS/USGS query APIs
return current state only, so a true historical snapshot cannot be
captured).

Rolled-back states in morning-1:

- GDACS M 7.7 (eventid 1474477): first episode at **Orange** (score 2) —
  the Orange→Red movement between the mornings is the ▲ ESCALATED case.
- USGS M 7.7 (us7000pn9s): PAGER not yet issued (``alert: null``), early
  significance, pre-review alias set and placename.
- GDACS DRC flood (eventid 1103210): first episode at **Red** (score 3) —
  the real capture's Orange makes the Red→Orange movement the ▽ DOWNGRADED
  case.

``reliefweb.xml`` and ``assessment.json`` in the morning directories are
static committed files, not derived here.
"""

import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
CUTOFF_GDACS = "2025-03-28T06:30:00"
CUTOFF_USGS_MS = 1_743_143_400_000  # 2025-03-28T06:30:00Z


def derive_gdacs(payload: dict) -> dict:
    features = []
    for feature in payload["features"]:
        properties = feature["properties"]
        if properties["fromdate"] > CUTOFF_GDACS:
            continue  # not yet occurred at the snapshot instant
        feature = json.loads(json.dumps(feature))  # deep copy
        properties = feature["properties"]
        if properties["eventid"] == 1474477:  # Mandalay M 7.7 — first episode Orange
            properties.update(
                alertlevel="Orange",
                episodealertlevel="Orange",
                alertscore=2,
                datemodified="2025-03-28T06:26:00",
            )
        if properties["eventid"] == 1103210:  # DRC flood — first episode Red
            properties.update(
                alertlevel="Red",
                episodealertlevel="Red",
                alertscore=3,
                episodeid=1,
                datemodified="2025-03-28T02:00:00",
            )
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def derive_usgs(payload: dict) -> dict:
    features = []
    for feature in payload["features"]:
        properties = feature["properties"]
        if properties["time"] > CUTOFF_USGS_MS:
            continue
        feature = json.loads(json.dumps(feature))
        properties = feature["properties"]
        if feature["id"] == "us7000pn9s":  # Mandalay M 7.7 — PAGER pending
            properties.update(
                alert=None,
                sig=910,
                updated=1_743_143_100_000,  # 06:25 UTC
                ids=",us7000pn9s,usauto7000pn9s,",
                place="Burma (Myanmar)",
                title="M 7.7 - Burma (Myanmar)",
                status="automatic",
            )
        features.append(feature)
    payload = json.loads(json.dumps(payload))
    payload["features"] = features
    payload["metadata"]["count"] = len(features)
    return payload


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {path} ({len(payload.get('features', []))} features)")


def main() -> None:
    eventful = HERE / "eventful"
    gdacs = json.loads((eventful / "gdacs.json").read_text())
    usgs = json.loads((eventful / "usgs.json").read_text())

    write(HERE / "morning-1" / "gdacs.json", derive_gdacs(gdacs))
    write(HERE / "morning-1" / "usgs.json", derive_usgs(usgs))

    (HERE / "morning-2").mkdir(exist_ok=True)
    for feed in ("gdacs.json", "usgs.json"):
        shutil.copyfile(eventful / feed, HERE / "morning-2" / feed)
        print(f"copied eventful/{feed} -> morning-2/{feed}")


if __name__ == "__main__":
    main()
