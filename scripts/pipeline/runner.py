"""One invocation = one fetch cycle (docs/SLICE-V1.md, extended by V2).

fetch → normalise → merge (tiers, PRD §6) → gate → link umbrellas → diff
against the store (classified, PRD §4 #5) → persist → render. The verdict
(``CHANGED``/``QUIET``) decides whether the dashboard redeploys and whether
the daily model run has anything to say.

Nothing here calls a model (CLAUDE.md). The daily sitrep orchestration —
the only place a model wakes — lives outside ``scripts/`` in ``agent/``
and reuses ``run_cycle`` + ``render.write_sitrep``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pipeline import details, diff, fetch, gate, merge, normalise, reliefweb, render, store


def run_cycle(replay_dir: Path | None, data_dir: Path) -> dict:
    """One deterministic cycle; returns ``{"manifest", "store", "candidates"}``.

    ``candidates`` are the gated-out Greens the model may promote with an
    editorial label — computed here so the caller never re-runs the gate.
    """
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    previous_manifest = store.load_manifest(data_dir) or {}
    previous_feeds = previous_manifest.get("feeds", {})

    gdacs_payload, gdacs_fetched_at, gdacs_status = fetch.fetch_gdacs(replay_dir)
    usgs_payload, usgs_fetched_at, usgs_status = fetch.fetch_usgs(replay_dir)
    umbrellas, reliefweb_fetched_at, reliefweb_status = reliefweb.ReliefWebRSS().fetch(replay_dir)

    gdacs_events = normalise.normalise_gdacs(gdacs_payload or {})
    usgs_events = normalise.normalise_usgs(usgs_payload or {})

    merged = merge.merge_records(gdacs_events + usgs_events)
    gated = gate.apply_gate(merged)
    merge.annotate_possible_related(gated)
    reliefweb.link_umbrellas(gated, umbrellas)
    candidates = gate.green_candidates(merged)

    fetched_sources = set()
    if gdacs_status == fetch.STATUS_OK:
        fetched_sources.add("gdacs")
    if usgs_status == fetch.STATUS_OK:
        fetched_sources.add("usgs")

    stored = store.load_events(data_dir)
    verdict, changes, updated = diff.diff_and_update(
        stored,
        gated,
        now_iso,
        all_events=merged,
        fetched_sources=fetched_sources,
        confirm_withdrawal=details.make_withdrawal_confirmer(replay_dir),
    )

    def _feed(status: str, fetched_at: str, name: str, counts: dict) -> dict:
        if status != fetch.STATUS_OK:
            # The chip shows the last *success*, not the last attempt.
            fetched_at = (previous_feeds.get(name) or {}).get("fetched_at")
        return {"status": status, "fetched_at": fetched_at, **counts}

    manifest = {
        "run_at": now_iso,
        "run_number": (previous_manifest.get("run_number") or 0) + 1,
        "mode": f"replay:{replay_dir}" if replay_dir is not None else "live",
        "verdict": verdict,
        "feeds": {
            "gdacs": _feed(
                gdacs_status,
                gdacs_fetched_at,
                "gdacs",
                {
                    "count_fetched": len(gdacs_events),
                    "count_gated": sum(1 for e in gated if "gdacs" in e["sources"]),
                },
            ),
            "usgs": _feed(
                usgs_status,
                usgs_fetched_at,
                "usgs",
                {
                    "count_fetched": len(usgs_events),
                    "count_gated": sum(1 for e in gated if "usgs" in e["sources"]),
                },
            ),
            "reliefweb": _feed(
                reliefweb_status,
                reliefweb_fetched_at,
                "reliefweb",
                {
                    "count_fetched": len(umbrellas),
                    "count_gated": sum(
                        1 for e in gated for u in e.get("umbrellas", []) if u
                    ),
                },
            ),
        },
        "changes": changes,
        "active_events": sorted(
            event_id for event_id, r in updated.items() if r.get("status") == "active"
        ),
        # Carried forward, not recomputed here: scripts/deploy.py owns this
        # key and patches it in place after a real deploy. Without carrying
        # it forward, the next cycle's store.save() would wipe it and every
        # cycle would look like changed content (V3 integration deviation).
        "deploy_state": previous_manifest.get("deploy_state", {}),
    }

    store.save(data_dir, updated, manifest)
    return {"manifest": manifest, "store": updated, "candidates": candidates}


def run_once(replay_dir: Path | None, data_dir: Path, out_path: Path) -> dict:
    """The model-free monitor cycle: run + deterministic render."""
    cycle = run_cycle(replay_dir, data_dir)
    render.write_sitrep(cycle["store"], cycle["manifest"], out_path)
    return cycle["manifest"]
