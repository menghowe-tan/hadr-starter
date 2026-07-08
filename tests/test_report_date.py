"""Cron-margin date stamping across the SGT/UTC day boundary."""

from datetime import datetime, timedelta, timezone

from report_date import coverage_start, report_date


def test_cron_jitter_window_keeps_the_same_sgt_date():
    # scheduled 00:00 UTC; fires anywhere up to 00:20 UTC late
    for minute in (0, 5, 20):
        now = datetime(2025, 7, 30, 0, minute, tzinfo=timezone.utc)
        assert report_date(now).isoformat() == "2025-07-30"


def test_utc_evening_is_already_the_next_sgt_day():
    now = datetime(2025, 7, 29, 23, 59, tzinfo=timezone.utc)  # 07:59 SGT on the 30th
    assert report_date(now).isoformat() == "2025-07-30"
    assert report_date(now - timedelta(hours=8)).isoformat() == "2025-07-29"


def test_coverage_starts_at_previous_sitrep_or_24h():
    now = datetime(2025, 7, 30, 0, 30, tzinfo=timezone.utc)
    prev = datetime(2025, 7, 29, 0, 31, tzinfo=timezone.utc)
    assert coverage_start(now, prev) == prev
    assert coverage_start(now, None) == now - timedelta(hours=24)
