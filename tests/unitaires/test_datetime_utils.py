import pytest

from src.domain.datetime_utils import (
    normalize_date_iso,
    normalize_time_hhmm,
    parse_date_any,
    parse_french_date,
    to_french_date_label,
)


def test_parse_date_any_supported_formats():
    assert parse_date_any("2026-03-01").strftime("%Y-%m-%d") == "2026-03-01"
    assert parse_date_any("01/03/2026").strftime("%Y-%m-%d") == "2026-03-01"
    assert parse_date_any("2026/03/01").strftime("%Y-%m-%d") == "2026-03-01"


def test_normalize_date_iso():
    assert normalize_date_iso("01/03/2026") == "2026-03-01"


def test_normalize_time_hhmm_variants():
    assert normalize_time_hhmm("09:12:55") == "09:12"
    assert normalize_time_hhmm("8:05") == "08:05"
    assert normalize_time_hhmm("") == ""


def test_to_french_date_label():
    assert to_french_date_label("2026-03-01") == "01 mars 2026"


def test_parse_french_date_aliases_and_accents():
    assert parse_french_date("02 fevrier 2026").strftime("%Y-%m-%d") == "2026-02-02"
    assert parse_french_date("02 février 2026").strftime("%Y-%m-%d") == "2026-02-02"
    assert parse_french_date("03 août 2026").strftime("%Y-%m-%d") == "2026-08-03"
    assert parse_french_date("04 décembre 2026").strftime("%Y-%m-%d") == "2026-12-04"


def test_invalid_date_and_time_raise():
    with pytest.raises(ValueError):
        parse_date_any("03-01-2026")
    with pytest.raises(ValueError):
        normalize_time_hhmm("26:61")
    with pytest.raises(ValueError):
        parse_french_date("bad format")
