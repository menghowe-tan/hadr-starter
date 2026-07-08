"""Run semantics per PRD §7 — quiet, degraded, down. Deterministic; never calls a model.

The truth table:
- all feeds fresh                      -> ok        (publish; "all quiet" if verdict QUIET)
- one real-time feed stale/down        -> degraded  (publish with a banner naming lost hazards)
- GDACS AND USGS down (or store gone)  -> abort     (no sitrep; fail loudly; exit code 3)
ReliefWeb is days-latency by design: its absence degrades, never blocks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

REALTIME_FEEDS = ("gdacs", "usgs")

# Monitor-loop cadence (PRD §12 — decided in slice V3): 15 minutes on the
# real-time feeds, hourly on ReliefWeb. A feed is stale past 3x its cadence.
CADENCE_MINUTES = {"gdacs": 15, "usgs": 15, "reliefweb": 60}
STALE_MULTIPLIER = 3
# Persistent failure: >= 1 hour without a success on a real-time feed alerts.
DOWN_AFTER = timedelta(hours=1)

# Readers think in hazards, not feeds (product design §3).
LOST_HAZARDS = {
    "gdacs": (
        "cyclone, flood, volcano, drought and wildfire coverage is blind; "
        "earthquake coverage continues via USGS"
    ),
    "usgs": (
        "earthquake magnitude and PAGER detail is blind; "
        "earthquake alerts continue via GDACS"
    ),
    "reliefweb": "confirmed (Reported) impact figures are unavailable; estimates continue",
}

ABORT_EXIT_CODE = 3


def feed_state(name: str, feed: dict, now: datetime) -> str:
    """fresh | stale | down for one feed at time `now`."""
    if feed.get("status") == "down":
        return "down"
    last_raw = feed.get("fetched_at")
    if last_raw is None:
        return "down"
    age = now - datetime.fromisoformat(last_raw)
    if age >= DOWN_AFTER:
        return "down"
    if age > timedelta(minutes=CADENCE_MINUTES.get(name, 15) * STALE_MULTIPLIER):
        return "stale"
    return "fresh"


def evaluate(manifest: dict, now: datetime | None = None) -> dict:
    """The machine-readable health verdict workflows condition on."""
    now = now or datetime.now(timezone.utc)
    states = {
        name: feed_state(name, feed, now)
        for name, feed in manifest.get("feeds", {}).items()
    }
    realtime_down = [f for f in REALTIME_FEEDS if states.get(f) == "down"]
    if len(realtime_down) == len(REALTIME_FEEDS):
        status = "abort"
    elif any(state != "fresh" for state in states.values()):
        status = "degraded"
    else:
        status = "ok"
    impaired = sorted(name for name, s in states.items() if s != "fresh")
    return {
        "status": status,
        "feed_states": states,
        "impaired_feeds": impaired,
        "blind_hazards": [LOST_HAZARDS[f] for f in impaired],
        # >=1h without a real-time success raises the alert without waiting
        # for the morning run (PRD §7).
        "alert": bool(realtime_down),
    }
