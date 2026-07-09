"""Committed-JSON store: ``data/`` is the database (CLAUDE.md; PRD §3).

One file per canonical event under ``data/events/`` plus ``data/manifest.json``
describing the latest run; git history is the audit trail. Aged-out events
keep their files — nothing is deleted until a detail endpoint proves a
withdrawal (PRD §7), which is out of scope for V1.
"""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_NAME = "manifest.json"
EVENTS_DIR = "events"
NEWS_NAME = "news.json"


def load_events(data_dir: Path) -> dict[str, dict]:
    """Load stored event records keyed by ``event_id``."""
    events_dir = Path(data_dir) / EVENTS_DIR
    if not events_dir.is_dir():
        return {}
    records = {}
    for path in sorted(events_dir.glob("*.json")):
        record = json.loads(path.read_text())
        records[record["event_id"]] = record
    return records


def load_manifest(data_dir: Path) -> dict | None:
    path = Path(data_dir) / MANIFEST_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _dump(payload: dict) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def save(data_dir: Path, events: dict[str, dict], manifest: dict) -> None:
    """Write every event record and the run manifest."""
    data_dir = Path(data_dir)
    events_dir = data_dir / EVENTS_DIR
    events_dir.mkdir(parents=True, exist_ok=True)
    for event_id, record in events.items():
        (events_dir / f"{event_id}.json").write_text(_dump(record))
    (data_dir / MANIFEST_NAME).write_text(_dump(manifest))


def load_news(data_dir: Path) -> dict | None:
    """The last committed news-summary search (skills/news-summary/SKILL.md),
    or ``None`` if the skill has never run. Absence is not "checked, found
    nothing" — callers must tell the two apart."""
    path = Path(data_dir) / NEWS_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def save_news(
    data_dir: Path, checked_at: str, items: list[dict], searched: bool | None = None
) -> None:
    """Persist the day's news search so the model-free dashboard renderer
    can display it without ever calling a model itself. ``searched`` is
    ``None`` for a replayed/recorded assessment (unknown whether a live
    search happened), ``True``/``False`` for a live run — distinct from
    ``items`` being empty because nothing was worth surfacing."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {"checked_at": checked_at, "searched": searched, "items": items}
    (data_dir / NEWS_NAME).write_text(_dump(payload))
