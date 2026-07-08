"""Sitrep date stamping — SGT appears only in rendered views (PRD §8).

The sitrep workflow is scheduled at 00:00 UTC targeting an 08:30 SGT
publish; GitHub cron fires late, so a run starting anywhere in the
00:00–00:20 UTC window must still stamp the same SGT report date.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8), name="SGT")


def report_date(now_utc: datetime) -> date:
    """The SGT calendar date this run publishes under."""
    return now_utc.astimezone(SGT).date()


def coverage_start(now_utc: datetime, previous_sitrep_utc: datetime | None) -> datetime:
    """The sitrep window covers since the previous sitrep — our own stored
    state, never a rolling feed window (PRD §8). Falls back to 24h."""
    return previous_sitrep_utc or (now_utc - timedelta(hours=24))


if __name__ == "__main__":
    print(report_date(datetime.now(timezone.utc)).isoformat())
