"""One invocation = one fetch cycle (docs/SLICE-V1.md).

fetch → normalise → gate → diff against the store → persist → render.
The verdict (``CHANGED``/``QUIET``) is the whole point: it is what will
decide, in later slices, whether the dashboard redeploys and whether the
daily model run has anything to say.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pipeline import diff, fetch, gate, normalise, render, store


def run_once(
    replay_dir: Path | None,
    data_dir: Path,
    out_path: Path,
) -> dict:
    """Run one fetch cycle; returns the run manifest."""
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    gdacs_payload, gdacs_fetched_at = fetch.fetch_gdacs(replay_dir)
    usgs_payload, usgs_fetched_at = fetch.fetch_usgs(replay_dir)

    gdacs_events = normalise.normalise_gdacs(gdacs_payload)
    usgs_events = normalise.normalise_usgs(usgs_payload)

    gated = gate.apply_gate(gdacs_events + usgs_events)

    stored = store.load_events(data_dir)
    verdict, changes, updated = diff.diff_and_update(stored, gated, now_iso)

    manifest = {
        "run_at": now_iso,
        "mode": f"replay:{replay_dir}" if replay_dir is not None else "live",
        "verdict": verdict,
        "feeds": {
            "gdacs": {
                "fetched_at": gdacs_fetched_at,
                "count_fetched": len(gdacs_events),
                "count_gated": sum(1 for e in gated if e["source"] == "gdacs"),
            },
            "usgs": {
                "fetched_at": usgs_fetched_at,
                "count_fetched": len(usgs_events),
                "count_gated": sum(1 for e in gated if e["source"] == "usgs"),
            },
        },
        "changes": changes,
        "active_events": sorted(
            event_id for event_id, r in updated.items() if r.get("status") == "active"
        ),
    }

    store.save(data_dir, updated, manifest)
    render.render_dashboard(updated, manifest, out_path)
    return manifest
