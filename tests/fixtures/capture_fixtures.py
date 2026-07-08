"""Capture the replay fixtures from the historical query APIs.

Run manually (network required); the committed fixtures are the output of
this script, captured 2026-07-08. See tests/fixtures/README.md for what each
fixture contains and why.

    uv run tests/fixtures/capture_fixtures.py

- Eventful morning: 2025-03-28, the Myanmar M 7.7 earthquake (GDACS Red,
  PAGER red) plus an Orange flood and that day's Greens.
- Quiet morning: 2025-04-09 — only Green GDACS events and sub-threshold
  quakes; nothing clears the PRD §5 gate.

GDACS search is day-granular; USGS windows are 00:00-12:00 UTC ("the
morning"). Fixture files mirror the live feed shapes the pipeline polls
(GDACS ``EVENTS4APP`` event list, USGS summary GeoJSON).
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
UA = {"User-Agent": "hadr-starter fixture capture (github.com/menghowe-tan/hadr-starter)"}

GDACS_SEARCH = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
USGS_QUERY = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def get_json(url: str, params: dict) -> dict:
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def gdacs_day(from_date: str, to_date: str, alertlevel: str = "") -> list:
    payload = get_json(
        GDACS_SEARCH,
        {"fromDate": from_date, "toDate": to_date, "alertlevel": alertlevel, "eventlist": "", "country": ""},
    )
    return payload.get("features", [])


def usgs_morning(day: str) -> dict:
    return get_json(
        USGS_QUERY,
        {
            "format": "geojson",
            "starttime": f"{day}T00:00:00",
            "endtime": f"{day}T12:00:00",
            "minmagnitude": "4.5",
            "orderby": "time",
        },
    )


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {path} ({len(payload.get('features', []))} features)")


def main() -> None:
    # Eventful: GDACS defaults to Orange/Red in search results; add the same
    # day's Greens so the gate has something real to reject.
    eventful_gdacs = gdacs_day("2025-03-27", "2025-03-28") + gdacs_day(
        "2025-03-28", "2025-03-28", alertlevel="Green"
    )
    write(
        HERE / "eventful" / "gdacs.json",
        {"type": "FeatureCollection", "features": eventful_gdacs},
    )
    write(HERE / "eventful" / "usgs.json", usgs_morning("2025-03-28"))

    # Quiet: Greens only. The real 2025-04-09 also carried long-running
    # Orange situations (Kanlaon eruption, DRC floods); they are excluded
    # here because V1's fresh-state quiet demo needs a morning where nothing
    # clears the gate — recorded in implementation-notes.md.
    quiet_gdacs = gdacs_day("2025-04-09", "2025-04-09", alertlevel="Green")
    write(
        HERE / "quiet" / "gdacs.json",
        {"type": "FeatureCollection", "features": quiet_gdacs},
    )
    write(HERE / "quiet" / "usgs.json", usgs_morning("2025-04-09"))


if __name__ == "__main__":
    main()
