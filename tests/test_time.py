"""Unit: UTC normalisation for each timestamp format (PRD §8)."""

from pipeline.normalise import utc_from_epoch_ms, utc_from_gdacs


def test_gdacs_naive_string_is_declared_utc():
    assert utc_from_gdacs("2026-07-06T11:29:36") == "2026-07-06T11:29:36+00:00"


def test_gdacs_aware_string_converted_to_utc():
    assert utc_from_gdacs("2026-07-06T19:29:36+08:00") == "2026-07-06T11:29:36+00:00"


def test_usgs_epoch_ms_to_utc():
    assert utc_from_epoch_ms(1743141654000) == "2025-03-28T06:00:54+00:00"


def test_usgs_epoch_ms_keeps_sub_second_precision():
    assert utc_from_epoch_ms(1743142852715) == "2025-03-28T06:20:52.715000+00:00"


def test_epoch_zero():
    assert utc_from_epoch_ms(0) == "1970-01-01T00:00:00+00:00"
