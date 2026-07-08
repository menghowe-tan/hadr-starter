"""Per-event detail lookups: the only proof of deletion (PRD §7).

An event missing from a rolling window is **aged-out until proven
deleted**. This module builds the ``confirm_withdrawal(record) -> bool``
callable the diff uses to disambiguate:

- Replay mode: reads ``<fixture-dir>/details/<event_id>.json``; the file
  says ``{"deleted": true}`` when the capture confirmed a deletion. No
  file means no proof — aged-out.
- Live mode: queries the USGS per-event detail endpoint for USGS-lane
  events (a deleted event answers with ``"status": "deleted"`` or an
  HTTP 409). GDACS has no reliable deletion signal, so GDACS-only events
  are never called withdrawn — aged-out is the honest answer.

Detail fetches happen only for gated-in events that vanished (PRD §9:
polite polling — per-event detail fetches only when needed).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from pipeline.fetch import USER_AGENT


def _usgs_detail_url(record: dict) -> str | None:
    urls = record.get("urls") or {}
    detail = urls.get("details")
    if detail and "earthquake.usgs.gov" in detail:
        return detail
    return None


def _confirm_live(record: dict) -> bool:
    url = _usgs_detail_url(record)
    if url is None:
        return False  # no detail lane for this source: never assert deletion
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        # USGS answers 409 Conflict for deleted events.
        return error.code == 409
    except (OSError, ValueError):
        return False
    status = (payload.get("properties") or {}).get("status")
    return str(status).lower() == "deleted"


def make_withdrawal_confirmer(replay_dir: Path | None) -> Callable[[dict], bool]:
    if replay_dir is None:
        return _confirm_live

    def _confirm_replay(record: dict) -> bool:
        path = Path(replay_dir) / "details" / f"{record['event_id']}.json"
        if not path.is_file():
            return False
        return bool(json.loads(path.read_text()).get("deleted"))

    return _confirm_replay
