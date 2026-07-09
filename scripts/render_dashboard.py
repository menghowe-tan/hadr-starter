"""Render the live dashboard from data/ — deterministic, never calls a model.

Reads the committed store (data/manifest.json + data/events/*.json) and
writes out/dashboard/index.html: a Leaflet map (OSM tiles — an accepted
view-time dependency), markers coloured by alert level, the current event
list, and per-feed freshness stamps. Redeployed by the monitor loop on
every store change (PRD decision #18).
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import health
from pipeline import diff as pipeline_diff
from pipeline import store as pipeline_store
from pipeline.render import display_title

REPO_ROOT = Path(__file__).resolve().parent.parent

# Design tokens (product design §7), light / dark. GDACS Green/Orange/Red are
# the only alert bands the design specifies; USGS PAGER yellow buckets with
# Green (no dedicated token) rather than invent a fourth colour.
ALERT_COLOURS = {"Red": "#C0392B", "Orange": "#B85B08", "Green": "#2E7D32"}


def load_store(data_dir: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((data_dir / "manifest.json").read_text())
    all_events = (json.loads(p.read_text()) for p in sorted((data_dir / "events").glob("*.json")))
    events = [e for e in all_events if e.get("status") == "active"]
    return manifest, events


def alert_word(event: dict) -> str:
    """GDACS/PAGER alert level, collapsed to the three design tokens."""
    rank = pipeline_diff.effective_level_rank(event)
    if rank >= pipeline_diff.LEVEL_RANK["red"]:
        return "Red"
    if rank >= pipeline_diff.LEVEL_RANK["orange"]:
        return "Orange"
    return "Green"


def marker_payload(event: dict, changes_by_id: dict) -> dict:
    """The slice of a canonical event the map needs — derived, never invented."""
    change = changes_by_id.get(event["event_id"])
    change_text = None
    if change:
        change_text = change["change"] + (f": {change['detail']}" if change.get("detail") else "")
    return {
        "id": event["event_id"],
        "hazard": event["hazard"],
        "name": display_title(event),
        "level": alert_word(event),
        "lat": event["lat"],
        "lon": event["lon"],
        # V1/V2's canonical event has no forecast-track field yet (GDACS
        # cyclone tracks are future work); the map just draws no polyline.
        "track": event.get("track") or [],
        "magnitude": event.get("magnitude"),
        "change": change_text,
        "headline": event.get("gate_reason"),
        "anchor": event["event_id"],
    }


def news_panel(news: dict | None) -> str:
    """skills/news-summary/SKILL.md, read straight off the committed store —
    this script never calls a model; it only displays what the last daily
    sitrep run already found and wrote to ``data/news.json``. Always shown,
    never silently omitted: whether the skill has run at all is itself
    something this dashboard should state, not leave the reader to guess."""
    if news is None:
        return (
            "<h2>News mentions</h2>"
            '<p class="news-meta">The news-summary skill has not run yet.</p>'
        )
    items = news.get("items") or []
    checked = html.escape(news.get("checked_at") or "unknown time")
    if items:
        rows = "".join(
            f'<li class="news-item"><a href="{html.escape(i["url"])}" target="_blank" '
            f'rel="noopener">{html.escape(i["headline"] or i["url"])}</a>'
            f'<div class="news-meta">{html.escape(i.get("source") or "")}'
            + (f' · {html.escape(i["published_at"])}' if i.get("published_at") else "")
            + "</div></li>"
            for i in items
        )
    elif news.get("searched") is False:
        rows = '<li class="news-meta">The model did not search last run.</li>'
    else:
        rows = '<li class="news-meta">No relevant coverage found in the last check.</li>'
    return (
        '<h2>News mentions</h2>'
        f'<p class="news-meta">Checked {checked} — unverified web search, not '
        "confirmed by this pipeline.</p>"
        f'<ul class="news-list">{rows}</ul>'
    )


def render(manifest: dict, events: list[dict], now: datetime, news: dict | None = None) -> str:
    verdict = health.evaluate(manifest, now)
    changes_by_id = {c["event_id"]: c for c in manifest.get("changes", [])}
    markers = [marker_payload(e, changes_by_id) for e in events]
    feeds_meta = {
        name: {
            "fetched_at": feed.get("fetched_at"),
            "state": verdict["feed_states"].get(name, "down"),
        }
        for name, feed in manifest.get("feeds", {}).items()
    }
    banner = ""
    if verdict["status"] == "degraded":
        lost = "; ".join(verdict["blind_hazards"])
        banner = (
            '<div class="banner" role="alert"><strong>Degraded coverage:</strong> '
            f"{html.escape(lost)}.</div>"
        )
    payload = json.dumps(
        {"markers": markers, "feeds": feeds_meta, "colours": ALERT_COLOURS}
    )
    generated = now.isoformat(timespec="seconds")
    run_utc = html.escape(manifest.get("run_at", ""))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Monitor — live dashboard</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {{ --ground:#F7F9FB; --surface:#FFF; --ink:#1B2733; --muted:#5B6B7A;
  --line:#D7DEE6; --accent:#0E5FA8; --orange:#B85B08; --orange-wash:#FBEEDF; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ground:#0F151C; --surface:#161E27; --ink:#D9E2EB; --muted:#8FA0B0;
    --line:#2B3846; --accent:#7FB3E3; --orange:#EDA75B; --orange-wash:#33230F; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--ground); color:var(--ink);
  font-family:system-ui,sans-serif; display:flex; flex-direction:column; height:100vh }}
header {{ padding:10px 16px; border-bottom:1px solid var(--line); display:flex;
  flex-wrap:wrap; gap:6px 18px; align-items:baseline; background:var(--surface) }}
header h1 {{ font-size:16px; margin:0 }}
.stamp, .chip {{ font-family:ui-monospace,monospace; font-size:12px; color:var(--muted) }}
.chip .dot {{ display:inline-block; width:8px; height:8px; border-radius:50%;
  margin-right:4px; vertical-align:baseline }}
.banner {{ background:var(--orange-wash); color:var(--orange);
  padding:8px 16px; font-size:14px }}
main {{ display:flex; flex:1; min-height:0 }}
#map {{ flex:1; background:var(--ground) }}
aside {{ width:320px; max-width:40%; overflow-y:auto; border-left:1px solid var(--line);
  background:var(--surface); padding:10px }}
aside h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); margin:4px 0 8px }}
.event {{ display:block; width:100%; text-align:left; border:1px solid var(--line);
  border-radius:8px; padding:8px 10px; margin-bottom:8px; background:none;
  color:inherit; font:inherit; cursor:pointer }}
.event:focus {{ outline:2px solid var(--accent) }}
.event .lvl {{ font-family:ui-monospace,monospace; font-size:11px; font-weight:700 }}
.news-list {{ list-style:none; margin:0 0 4px; padding:0 }}
.news-item {{ margin:0 0 8px; font-size:13px }}
.news-item a {{ color:var(--accent); text-decoration:none; font-weight:600 }}
.news-meta {{ font-family:ui-monospace,monospace; font-size:11px; color:var(--muted); margin:2px 0 0 }}
.tile-notice {{ position:absolute; z-index:1000; top:10px; left:50px;
  background:var(--surface); border:1px solid var(--line); border-radius:6px;
  padding:6px 10px; font-size:12px; color:var(--muted); display:none }}
</style>
</head>
<body>
<header>
  <h1>HADR Monitor</h1>
  <span class="stamp">store run {run_utc} · rendered {html.escape(generated)}</span>
  <span id="feed-chips"></span>
</header>
{banner}
<main>
  <div id="map" role="application" aria-label="Event map">
    <div class="tile-notice" id="tile-notice">Base map unavailable — showing plain grid; event data unaffected.</div>
  </div>
  <aside aria-label="Current events, mirroring the map markers">
    <h2>Current events</h2>
    <div id="event-list"></div>
    {news_panel(news)}
  </aside>
</main>
<script id="store" type="application/json">{payload}</script>
<script>
const DATA = JSON.parse(document.getElementById("store").textContent);
const map = L.map("map", {{ worldCopyJump: true }}).setView([20, 60], 2);
const tiles = L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
  maxZoom: 12, attribution: "&copy; OpenStreetMap contributors"
}}).addTo(map);

// Failure mode: if tiles never load, fall back to a plain graticule ground —
// the data never disappears with the basemap (product design §6).
let tileOK = false, tileErrs = 0;
tiles.on("load tileload", () => {{ tileOK = true; }});
tiles.on("tileerror", () => {{
  if (tileOK || ++tileErrs < 4) return;
  map.removeLayer(tiles);
  for (let lat = -80; lat <= 80; lat += 20)
    L.polyline([[lat, -180], [lat, 180]], {{ color: "#9AA7B4", weight: .5, interactive: false }}).addTo(map);
  for (let lon = -180; lon <= 180; lon += 20)
    L.polyline([[-85, lon], [85, lon]], {{ color: "#9AA7B4", weight: .5, interactive: false }}).addTo(map);
  document.getElementById("tile-notice").style.display = "block";
}});

function ago(iso, now) {{
  if (!iso) return "never";
  const mins = Math.max(0, Math.round((now - new Date(iso)) / 60000));
  return mins < 60 ? mins + " min ago" : Math.round(mins / 60 * 10) / 10 + " h ago";
}}
const STATE_COLOUR = {{ fresh: "#2E7D32", stale: "#B85B08", down: "#C0392B" }};
const now = Date.now();
document.getElementById("feed-chips").innerHTML = Object.entries(DATA.feeds)
  .map(([name, f]) =>
    `<span class="chip" title="${{f.state}}"><span class="dot" style="background:${{STATE_COLOUR[f.state]}}"></span>` +
    `${{name.toUpperCase()}} ${{ago(f.fetched_at, now)}}${{f.state !== "fresh" ? " (" + f.state + ")" : ""}}</span> `
  ).join("");

const listEl = document.getElementById("event-list");
DATA.markers.forEach((ev, i) => {{
  const colour = DATA.colours[ev.level] || "#5B6B7A";
  if (ev.track.length > 1) {{
    // Track, not cone: cones imply a certainty model we don't have (§6).
    L.polyline(ev.track, {{ color: colour, dashArray: "6 6", weight: 2 }}).addTo(map);
  }}
  const marker = L.circleMarker([ev.lat, ev.lon], {{
    radius: ev.level === "Red" ? 10 : 8, color: colour, fillColor: colour, fillOpacity: .7
  }}).addTo(map);
  const mag = ev.magnitude ? ` · M${{ev.magnitude}}` : "";
  marker.bindPopup(
    `<strong>${{ev.name}}</strong><br>` +
    `<span style="color:${{colour}};font-weight:700">${{ev.level}}</span> ${{ev.hazard}}${{mag}}<br>` +
    (ev.headline ? ev.headline + "<br>" : "") +
    (ev.change ? "Changed: " + ev.change + "<br>" : "") +
    `<a href="../sitrep/index.html#${{ev.anchor}}">Open in sitrep</a>`
  );
  const btn = document.createElement("button");
  btn.className = "event";
  btn.innerHTML = `<span class="lvl" style="color:${{colour}}">${{ev.level.toUpperCase()}}</span> ` +
    `${{ev.hazard}} — ${{ev.name}}${{mag}}`;
  btn.addEventListener("click", () => {{ map.setView([ev.lat, ev.lon], 5); marker.openPopup(); }});
  listEl.appendChild(btn);
}});
if (!DATA.markers.length)
  listEl.innerHTML = '<p style="color:var(--muted)">All quiet — no events in the store.</p>';
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "dashboard")
    parser.add_argument("--now", type=datetime.fromisoformat, default=None)
    args = parser.parse_args(argv)
    if not (args.data / "manifest.json").exists():
        print(f"store unreadable: {args.data}/manifest.json missing", file=sys.stderr)
        return health.ABORT_EXIT_CODE
    manifest, events = load_store(args.data)
    news = pipeline_store.load_news(args.data)
    page = render(manifest, events, args.now or datetime.now(timezone.utc), news)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.html").write_text(page)
    print(f"wrote {args.out / 'index.html'} ({len(events)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
