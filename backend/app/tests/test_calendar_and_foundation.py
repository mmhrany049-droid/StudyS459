"""Unit tests: Jalali calendar, week order, cascade, config registry.

study_system_v3_docs/11: "Unit tests: Jalali conversion, topic cascade, ..."
study_system_v2_2_docs/13: "UI هیچ تاریخ میلادی نشان نمیدهد" + "تیک فصل همه فرزندان را تدریسشده میکند".
"""

from __future__ import annotations

import datetime as dt

import pytest

from app import config
from app.core import jalali as jl
from app.core.timeutil import week_start, week_end, today_local, week_label_fa


# ---------------------------------------------------------------------------
# Jalali conversion (verified against jalaali-js day-by-day for 1990..2035)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "gregorian,jalali",
    [
        ((2025, 9, 15), (1404, 6, 24)),
        ((2026, 9, 17), (1405, 6, 26)),
        ((2025, 3, 21), (1404, 1, 1)),
        ((2026, 3, 21), (1405, 1, 1)),
        ((2024, 3, 20), (1403, 1, 1)),
        ((2000, 1, 1), (1378, 10, 11)),
    ],
)
def test_round_trip(gregorian, jalali):
    assert jl.gregorian_to_jalali(*gregorian) == jalali
    assert jl.jalali_to_gregorian(*jalali) == gregorian


@pytest.mark.parametrize("year", [1403, 1408, 1412, 1416])
def test_known_leap_years_have_30_day_esfand(year):
    assert jl.is_leap_jalali(year) is True
    assert jl.jalali_month_length(year, 12) == 30


@pytest.mark.parametrize("year", [1400, 1401, 1402, 1404, 1405, 1406, 1407, 1409])
def test_common_years_have_29_day_esfand(year):
    assert jl.is_leap_jalali(year) is False
    assert jl.jalali_month_length(year, 12) == 29


def test_months_one_to_six_are_31_and_seven_to_eleven_are_30():
    for month in range(1, 7):
        assert jl.jalali_month_length(1405, month) == 31
    for month in range(7, 12):
        assert jl.jalali_month_length(1405, month) == 30


def test_persian_digits_and_parsing():
    assert jl.to_persian_digits("1405/06/26") == "۱۴۰۵/۰۶/۲۶"
    assert jl.normalize_digits("۱۴۰۵/۰۶/۲۶") == "1405/06/26"
    assert jl.parse_jalali("۱۴۰۵-۰۶-۲۶") == dt.date(2026, 9, 17)
    assert jl.format_jalali(dt.date(2026, 9, 17)) == "۱۴۰۵/۰۶/۲۶"


def test_invalid_dates_are_rejected_not_guessed():
    with pytest.raises(jl.JalaliError):
        jl.jalali_to_gregorian(1405, 12, 30)  # 1405 is not a leap year
    with pytest.raises(jl.JalaliError):
        jl.jalali_to_gregorian(1405, 13, 1)
    with pytest.raises(jl.JalaliError):
        jl.jalali_to_gregorian(1405, 7, 31)


def test_week_starts_on_saturday_and_ends_on_friday():
    # 2026-09-17 is a Thursday (پنجشنبه)
    day = dt.date(2026, 9, 17)
    start, end = week_start(day), week_end(day)
    assert start.weekday() == jl.SATURDAY
    assert end.weekday() == jl.FRIDAY
    assert (end - start).days == 6
    assert week_label_fa(start).startswith("شنبه")


def test_jalali_error_is_a_value_error():
    assert issubclass(jl.JalaliError, ValueError)


# ---------------------------------------------------------------------------
# Config registry: no magic numbers, every value carries provenance
# ---------------------------------------------------------------------------

def test_every_param_has_provenance_and_evidence_level():
    assert len(config.PARAMS) > 100
    for key, param in config.PARAMS.items():
        assert param.provenance, f"{key} has no provenance"
        assert param.confidence, f"{key} has no evidence level"
        assert param.value is not None or key.endswith("_optional")


def test_priority_weights_sum_to_expected_budget():
    weights = {k: v.value for k, v in config.PARAMS.items() if k.startswith("priority.weight.")}
    positive = sum(v for k, v in weights.items() if "cost" not in k and "saturation" not in k)
    assert 0.9 <= positive <= 1.05, positive


def test_model_version_is_pinned():
    assert config.MODEL_VERSION == "v3.0.0"
