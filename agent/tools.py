"""HADR tools plugged into the reusable harness.

Level 3 added fetch_feed; level 5 adds write_dashboard. Everything here is
project-specific; the harness knows nothing about disaster feeds.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import httpx

from harness import Tool

SGT = timezone(timedelta(hours=8))
OUT_DIR = Path(__file__).resolve().parent.parent / "out"

FEED_URLS = {
    "gdacs": "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP",
    "usgs": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
}


def _gdacs_utc(naive: str | None) -> str | None:
    # GDACS naive datetimes are UTC (PRD §8); declare it.
    return f"{naive}Z" if naive and not naive.endswith("Z") else naive


def _epoch_ms_utc(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _trim_gdacs(feature: dict) -> dict:
    p = feature.get("properties", {})
    lon, lat = (feature.get("geometry", {}).get("coordinates") or [None, None])[:2]
    return {
        "hazard": p.get("eventtype"),
        "event_id": p.get("eventid"),
        "episode_id": p.get("episodeid"),
        "glide": p.get("glide") or None,
        "name": p.get("name"),
        "alert_level": p.get("alertlevel"),
        "episode_alert_level": p.get("episodealertlevel"),
        "is_temporary": p.get("istemporary") == "true",
        "country": p.get("country"),
        "iso3": p.get("iso3"),
        "source": p.get("source"),
        "from_utc": _gdacs_utc(p.get("fromdate")),
        "to_utc": _gdacs_utc(p.get("todate")),
        "modified_utc": _gdacs_utc(p.get("datemodified")),
        "lat": lat,
        "lon": lon,
    }


def _trim_usgs(feature: dict) -> dict:
    p = feature.get("properties", {})
    coords = feature.get("geometry", {}).get("coordinates") or [None, None, None]
    return {
        "hazard": "EQ",
        "id": feature.get("id"),
        # Identity is the union of ids — the network prefix can flip (PRD §6).
        "ids": [i for i in (p.get("ids") or "").split(",") if i],
        "title": p.get("title"),
        "magnitude": p.get("mag"),
        "place": p.get("place"),
        "time_utc": _epoch_ms_utc(p.get("time")),
        "updated_utc": _epoch_ms_utc(p.get("updated")),
        "pager_alert": p.get("alert"),
        "sig": p.get("sig"),
        "tsunami_message_exists": bool(p.get("tsunami")),
        "status": p.get("status"),
        "lat": coords[1],
        "lon": coords[0],
        "depth_km": coords[2],
    }


def fetch_feed(feed: str) -> str:
    """Fetch one live feed, normalised to UTC and trimmed to what matters."""
    url = FEED_URLS.get(feed)
    if url is None:
        raise ValueError(f"unknown feed {feed!r}; expected one of {sorted(FEED_URLS)}")
    # Feeds redirect to their canonical host — follow, and log the final URL
    # (docs/solutions/2026-07-06-example-follow-redirects.md).
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    features = response.json().get("features", [])
    trim = _trim_gdacs if feed == "gdacs" else _trim_usgs
    return json.dumps(
        {
            "feed": feed,
            "fetched_utc": datetime.now(timezone.utc).isoformat(),
            "final_url": str(response.url),
            "event_count": len(features),
            "events": [trim(f) for f in features],
        }
    )


FETCH_FEED = Tool(
    name="fetch_feed",
    description=(
        "Fetch the current events from one live disaster feed. Call this for "
        "BOTH 'gdacs' (EU/UN multi-hazard alerts: earthquakes, cyclones, "
        "floods, volcanoes, drought, wildfires, with Green/Orange/Red alert "
        "levels) and 'usgs' (raw real-time earthquakes, past day, M4.5+) "
        "before assessing the situation. Timestamps are UTC."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "feed": {
                "type": "string",
                "enum": ["gdacs", "usgs"],
                "description": "Which feed to fetch.",
            }
        },
        "required": ["feed"],
    },
    fn=fetch_feed,
)

ALERT_COLOURS = {"Red": "#C0392B", "Orange": "#B85B08", "Green": "#2E7D32"}


def _event_card(i: int, ev: dict) -> str:
    level = ev.get("alert_level", "Green")
    colour = ALERT_COLOURS.get(level, "#5B6B7A")
    anchor = html.escape(str(ev.get("anchor") or f"event-{i}"))
    chips = (
        f'<span style="color:{colour};border:1px solid {colour};border-radius:999px;'
        f'padding:1px 8px;font-size:12px;font-weight:600">{html.escape(level)}</span> '
        f'<span style="color:#5B6B7A;font-size:12px">{html.escape(ev.get("hazard", ""))}</span>'
    )
    rows = []
    for label, key in (
        ("Where", "location"),
        ("When (UTC)", "time_utc"),
        ("Impact", "impact"),
        ("Changed", "change_note"),
        ("Sources", "sources"),
        ("Merge", "merge_confidence"),
    ):
        if ev.get(key):
            rows.append(
                f'<div style="font-size:13px;margin:2px 0"><strong>{label}:</strong> '
                f"{html.escape(str(ev[key]))}</div>"
            )
    return (
        f'<article id="{anchor}" style="border:1px solid #D7DEE6;border-radius:8px;'
        f'padding:12px 14px;margin:10px 0">'
        f"<div>{chips}</div>"
        f'<h3 style="margin:6px 0 4px;font-size:16px">{html.escape(ev.get("name", "Unnamed event"))}</h3>'
        f"{''.join(rows)}</article>"
    )


def write_dashboard(
    title: str,
    summary: str,
    events: list | None = None,
    blindspots: str | None = None,
    report_date: str | None = None,
) -> str:
    """Save the assessed events as a self-contained HTML page under out/."""
    date = report_date or datetime.now(SGT).date().isoformat()
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cards = "".join(_event_card(i, ev) for i, ev in enumerate(events or []))
    if not cards:
        cards = '<p style="color:#2E7D32;font-weight:600">All quiet — no events cleared the gate.</p>'
    blind = (
        f'<footer style="border-top:1px solid #D7DEE6;margin-top:24px;padding-top:10px;'
        f'color:#5B6B7A;font-size:13px"><strong>What this report cannot see:</strong> '
        f"{html.escape(blindspots)}</footer>"
        if blindspots
        else ""
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title></head>
<body style="margin:0;background:#F7F9FB;color:#1B2733;font-family:Georgia,serif">
<div style="max-width:680px;margin:0 auto;padding:32px 20px">
<header style="border-top:3px solid #0E5FA8;padding-top:10px">
<div style="font-family:ui-monospace,monospace;font-size:12px;color:#5B6B7A">
HADR SITREP · {html.escape(date)} SGT · generated {html.escape(generated)}</div>
<h1 style="font-family:system-ui,sans-serif;font-size:24px;margin:8px 0">{html.escape(title)}</h1>
</header>
<section><p style="font-size:17px;line-height:1.6">{html.escape(summary)}</p></section>
<section>{cards}</section>
{blind}
</div></body></html>
"""
    sitrep_dir = OUT_DIR / "sitrep"
    sitrep_dir.mkdir(parents=True, exist_ok=True)
    path = sitrep_dir / f"{date}.html"
    path.write_text(page)
    (sitrep_dir / "index.html").write_text(page)
    return f"wrote {path} ({len(events or [])} events) and sitrep/index.html"


WRITE_DASHBOARD = Tool(
    name="write_dashboard",
    description=(
        "Save your finished assessment as a self-contained HTML page (the "
        "sitrep). Call this exactly once, after fetching and assessing the "
        "feeds. `summary` is the plain-language layer: no acronyms, no feed "
        "names. Order `events` by severity, escalations first. Label every "
        "impact figure Estimated or Reported inside the `impact` text. Put "
        "coverage limits (tsunami warnings, ReliefWeb lag) in `blindspots`."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {
                "type": "string",
                "description": "Plain-language summary, ~5 sentences.",
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "hazard": {"type": "string"},
                        "alert_level": {
                            "type": "string",
                            "enum": ["Red", "Orange", "Green"],
                        },
                        "location": {"type": "string"},
                        "time_utc": {"type": "string"},
                        "impact": {
                            "type": "string",
                            "description": "Figures labelled Estimated or Reported.",
                        },
                        "change_note": {"type": "string"},
                        "sources": {"type": "string"},
                        "merge_confidence": {"type": "string"},
                        "anchor": {
                            "type": "string",
                            "description": "Stable id for deep links, e.g. the GDACS event id or USGS id.",
                        },
                    },
                    "required": ["name", "hazard", "alert_level"],
                },
            },
            "blindspots": {"type": "string"},
            "report_date": {
                "type": "string",
                "description": "YYYY-MM-DD (SGT). Defaults to today.",
            },
        },
        "required": ["title", "summary"],
    },
    fn=write_dashboard,
)

# --- web_search: a keyless alternative to Anthropic's server web_search ----
#
# skills/news-summary/SKILL.md used to lean on the API's native
# ``web_search_20250305`` server tool, which only runs against a live
# ``ANTHROPIC_API_KEY`` (and its billing). This local tool needs no key: it
# queries DuckDuckGo's HTML endpoint over plain httpx and parses the results,
# so the skill runs through the harness's ordinary tool loop against any model
# backend — including a keyless relay behind ``ANTHROPIC_BASE_URL``. The
# trade-off is that we now depend on an unversioned HTML shape rather than a
# documented API; ``_parse_ddg`` is deliberately forgiving and returns
# whatever it can recognise.

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
# A browser-ish UA — the HTML endpoint returns an empty page to an obvious bot.
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _clean_ddg_url(href: str) -> str:
    """DuckDuckGo wraps result links as ``//duckduckgo.com/l/?uddg=<enc>``;
    unwrap to the real destination. Pass anything else through unchanged."""
    if "uddg=" not in href:
        return href
    params = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    target = params.get("uddg", [None])[0]
    return urllib.parse.unquote(target) if target else href


class _DDGParser(HTMLParser):
    """Pull ``{title, url, snippet}`` out of DuckDuckGo's HTML result list."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict] = []
        self._grab: str | None = None  # 'title' | 'snippet' | None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        classes = dict(attrs).get("class", "") or ""
        if tag == "a" and "result__a" in classes:
            self.results.append(
                {"title": "", "url": _clean_ddg_url(dict(attrs).get("href", "")), "snippet": ""}
            )
            self._grab = "title"
        elif "result__snippet" in classes and self.results:
            self._grab = "snippet"

    def handle_endtag(self, tag: str) -> None:
        # Titles live inside one <a>; snippets inside one <a>/<div>. Either way
        # the run of text we care about ends at the next closing tag.
        self._grab = None

    def handle_data(self, data: str) -> None:
        if self._grab and self.results:
            self.results[-1][self._grab] += data


def _parse_ddg(html_text: str, max_results: int) -> list[dict]:
    parser = _DDGParser()
    parser.feed(html_text)
    results = []
    for item in parser.results:
        title = item["title"].strip()
        url = item["url"].strip()
        if not title or not url:
            continue
        results.append({"title": title, "url": url, "snippet": item["snippet"].strip()})
        if len(results) >= max_results:
            break
    return results


def web_search(query: str, max_results: int = 5) -> str:
    """Search the live web (DuckDuckGo, no API key) and return ranked hits."""
    response = httpx.post(
        DDG_HTML_URL,
        data={"q": query},
        headers={"User-Agent": _UA},
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    results = _parse_ddg(response.text, max_results)
    return json.dumps({"query": query, "result_count": len(results), "results": results})


WEB_SEARCH = Tool(
    name="web_search",
    description=(
        "Search the live web and get back a ranked list of results, each with "
        "a title, URL, and snippet. No API key required. Use it to check "
        "recent news coverage of an event, or to look for a fast-moving story "
        "the disaster feeds haven't caught yet. Always keep the real source "
        "name and URL from a result — never invent either."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
            "max_results": {
                "type": "integer",
                "description": "How many results to return (default 5).",
            },
        },
        "required": ["query"],
    },
    fn=web_search,
)

TOOLS = [FETCH_FEED, WRITE_DASHBOARD, WEB_SEARCH]
