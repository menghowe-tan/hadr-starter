"""Minimal dashboard skeleton — V1's placeholder for the real surfaces.

Renders the current gated events (or the all-quiet statement) with run and
per-feed last-fetch stamps. Deliberately unstyled: real design tokens and
the Leaflet map are later slices (`docs/product-design.md`). Generated
views are never committed (CLAUDE.md) — this writes into the gitignored
``reports/`` directory by default.

SGT appears here and only here (PRD §8): internally everything is UTC.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")

_LEVEL_RANK = {"red": 0, "orange": 1, "yellow": 2}


def stamp(utc_iso: str) -> str:
    """Render a stored UTC instant as SGT with the UTC alongside."""
    moment = datetime.fromisoformat(utc_iso).astimezone(timezone.utc)
    sgt = moment.astimezone(SGT)
    return f"{sgt.strftime('%d %b %Y %H:%M')} SGT · {moment.strftime('%H:%M')} UTC"


def _event_rank(record: dict) -> tuple:
    level = record.get("alert_level") or record.get("episode_alert_level") or ""
    return (_LEVEL_RANK.get(level, 3), record.get("occurred_at") or "")


def _event_line(record: dict, change_by_id: dict[str, str]) -> str:
    level = (record.get("alert_level") or "none").upper()
    note = change_by_id.get(record["event_id"], "unchanged")
    parts = [
        f"[{html.escape(level)}]",
        html.escape(record.get("hazard") or ""),
        f"<strong>{html.escape(record.get('title') or record['event_id'])}</strong>",
        f"— {stamp(record['occurred_at'])}",
        f"— gate: {html.escape(record.get('gate_reason') or '')}",
        f"— {html.escape(record.get('source') or '')}",
        f"— <em>{html.escape(note)}</em>",
    ]
    return f"<li>{' '.join(parts)}</li>"


def render_dashboard(store: dict[str, dict], manifest: dict, out_path: Path) -> Path:
    active = sorted(
        (r for r in store.values() if r.get("status") == "active"), key=_event_rank
    )
    aged_out_now = [
        store[c["event_id"]] for c in manifest["changes"] if c["change"] == "aged-out"
    ]
    change_by_id = {c["event_id"]: c["change"] for c in manifest["changes"]}

    feed_lines = "".join(
        f"<li>{html.escape(feed)}: fetched {stamp(info['fetched_at'])} — "
        f"{info['count_fetched']} records, {info['count_gated']} past the gate</li>"
        for feed, info in manifest["feeds"].items()
    )

    if active:
        body = (
            f"<h2>Current events ({len(active)})</h2>"
            f"<ul>{''.join(_event_line(r, change_by_id) for r in active)}</ul>"
        )
    else:
        body = (
            "<h2>All quiet</h2>"
            "<p>No events cleared the gate. The pipeline ran and found nothing "
            "— feed health above accounts for the silence.</p>"
        )

    if aged_out_now:
        body += (
            "<h2>No longer current</h2><ul>"
            + "".join(
                f"<li>{html.escape(r.get('title') or r['event_id'])} — aged out of the "
                "feed window (not withdrawn)</li>"
                for r in aged_out_now
            )
            + "</ul>"
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>HADR Monitor — dashboard skeleton</title>
</head>
<body>
<h1>HADR Monitor — dashboard skeleton</h1>
<p>Run {stamp(manifest['run_at'])} · verdict {html.escape(manifest['verdict'])} · mode {html.escape(manifest['mode'])}</p>
<h2>Feed health</h2>
<ul>{feed_lines}</ul>
{body}
<hr>
<p><small>Slice V1 skeleton — generated view, never committed; deploys externally in V3.</small></p>
</body>
</html>
"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page)
    return out_path
