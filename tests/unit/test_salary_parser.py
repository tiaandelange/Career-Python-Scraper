from decimal import Decimal

import pytest

from job_scout.services.salary import parse_salary_text, to_monthly


@pytest.mark.parametrize(
    "text,currency,period,min_m,max_m",
    [
        ("R70,000 per month", "ZAR", "monthly", Decimal("70000"), Decimal("70000")),
        ("ZAR 70k pm", "ZAR", "monthly", Decimal("70000"), Decimal("70000")),
        ("$80,000–$120,000 per year", "USD", "annual", Decimal("80000") / 12, Decimal("120000") / 12),
        ("€5,000/month", "EUR", "monthly", Decimal("5000"), Decimal("5000")),
        ("AUD 150,000 p.a.", "AUD", "annual", Decimal("150000") / 12, Decimal("150000") / 12),
        ("£500/day", "GBP", "daily", to_monthly(Decimal("500"), "daily"), to_monthly(Decimal("500"), "daily")),
        ("$60/hour", "USD", "hourly", to_monthly(Decimal("60"), "hourly"), to_monthly(Decimal("60"), "hourly")),
        ("from R80,000 per month", "ZAR", "monthly", Decimal("80000"), None),
        ("USD 90k per year", "USD", "annual", Decimal("90000") / 12, Decimal("90000") / 12),
    ],
)
def test_salary_formats(text, currency, period, min_m, max_m):
    snap = parse_salary_text(text)
    assert snap.published is True
    assert snap.currency == currency
    assert snap.period == period
    if min_m is not None:
        assert snap.min_monthly == min_m.quantize(Decimal("0.01")) if snap.period != "monthly" else snap.min_monthly == min_m or abs(snap.min_monthly - min_m) < Decimal("0.05")
    else:
        assert snap.min_monthly is None
    if max_m is None:
        assert snap.max_monthly is None or snap.min_monthly is not None


def test_up_to_has_no_lower_bound():
    snap = parse_salary_text("up to R90,000 per month")
    assert snap.published is True
    assert snap.min_monthly is None
    assert snap.max_monthly == Decimal("90000")
    assert "up_to_has_no_lower_bound" in snap.parse_notes


def test_glassdoor_estimate_rejected():
    snap = parse_salary_text("Glassdoor estimate $120,000 per year")
    assert snap.published is False
    assert snap.estimated is True


def test_range_lower_bound_used():
    snap = parse_salary_text("R60,000-R90,000 per month")
    assert snap.min_monthly == Decimal("60000")
    assert snap.max_monthly == Decimal("90000")


def test_hourly_and_daily_math():
    hourly = to_monthly(Decimal("50"), "hourly")
    assert hourly == (Decimal("50") * 40 * 52 / 12).quantize(Decimal("0.01"))
    daily = to_monthly(Decimal("400"), "daily")
    assert daily == (Decimal("400") * 5 * 52 / 12).quantize(Decimal("0.01"))
