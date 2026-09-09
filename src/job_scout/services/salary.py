"""Parse employer-published salary text. Never invent a lower bound."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from job_scout.models.job import SalarySnapshot

_PERIOD_ALIASES = {
    "hour": "hourly",
    "hourly": "hourly",
    "hr": "hourly",
    "ph": "hourly",
    "/h": "hourly",
    "/hr": "hourly",
    "day": "daily",
    "daily": "daily",
    "pd": "daily",
    "p/d": "daily",
    "/d": "daily",
    "week": "weekly",
    "weekly": "weekly",
    "pw": "weekly",
    "p/w": "weekly",
    "month": "monthly",
    "monthly": "monthly",
    "pm": "monthly",
    "p/m": "monthly",
    "pcm": "monthly",
    "per month": "monthly",
    "year": "annual",
    "yearly": "annual",
    "annual": "annual",
    "annum": "annual",
    "pa": "annual",
    "p.a": "annual",
    "p.a.": "annual",
    "fy": "annual",
    "per year": "annual",
    "per annum": "annual",
}

_CURRENCY_WORDS = {
    "zar": "ZAR",
    "rand": "ZAR",
    "rands": "ZAR",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "aud": "AUD",
    "cad": "CAD",
    "nzd": "NZD",
    "chf": "CHF",
    "jpy": "JPY",
    "nok": "NOK",
    "sek": "SEK",
    "dkk": "DKK",
    "pln": "PLN",
}

_SYMBOLS = {
    "€": "EUR",
    "£": "GBP",
    "r": "ZAR",
    "a$": "AUD",
    "au$": "AUD",
    "c$": "CAD",
    "nz$": "NZD",
    "$": "USD",
}

_NUMBER = r"(?:(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?:[.,]\d+)?|\d+(?:\.\d+)?)\s*[kKmM]?"
_RANGE_SEP = r"(?:\s*(?:-|–|—|to|and)\s*)"


def _to_decimal(raw: str) -> Decimal | None:
    text = raw.strip().lower().replace(" ", "").replace(",", "")
    multiplier = Decimal("1")
    if text.endswith("k"):
        multiplier = Decimal("1000")
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = Decimal("1000000")
        text = text[:-1]
    if text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return Decimal(text) * multiplier
    except (InvalidOperation, ValueError):
        return None


def detect_currency(text: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.upper()
    lowered = text.lower()
    for word, code in _CURRENCY_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            return code
    if re.search(r"\baud\b|australian\s+dollar|a\$", lowered):
        return "AUD"
    if "zar" in lowered or re.search(r"\brand\b", lowered) or re.search(r"\bR[\s]?[\d]", text):
        return "ZAR"
    if "€" in text or "eur" in lowered:
        return "EUR"
    if "£" in text or "gbp" in lowered:
        return "GBP"
    if "$" in text:
        if re.search(r"\b(australia|aud)\b", lowered):
            return "AUD"
        if re.search(r"\b(canada|cad)\b", lowered):
            return "CAD"
        return "USD"
    if re.search(r"\bR[\d]", text) or re.search(r"\bR\s+\d", text):
        return "ZAR"
    return None


def detect_period(text: str, explicit: str | None = None) -> str:
    if explicit:
        key = explicit.lower().strip().replace(".", "")
        return _PERIOD_ALIASES.get(key, key)
    lowered = text.lower()
    for alias, period in sorted(_PERIOD_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias in lowered:
            return period
    # Bare South African "R70,000" in recruitment ads is typically monthly.
    if detect_currency(text) == "ZAR" and re.search(r"\bR?\s?\d", text) and "year" not in lowered:
        return "monthly"
    return "annual"


def to_monthly(amount: Decimal, period: str, policy: dict[str, Any] | None = None) -> Decimal:
    policy = policy or {}
    norm = (policy.get("normalisation") or {})
    hours = Decimal(str(norm.get("hourly_hours_per_week", 40)))
    days = Decimal(str(norm.get("daily_days_per_week", 5)))
    weeks = Decimal(str(norm.get("weeks_per_year", 52)))
    if period == "monthly":
        return amount
    if period == "annual":
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    if period == "weekly":
        return ((amount * weeks) / Decimal("12")).quantize(Decimal("0.01"))
    if period == "daily":
        return ((amount * days * weeks) / Decimal("12")).quantize(Decimal("0.01"))
    if period == "hourly":
        return ((amount * hours * weeks) / Decimal("12")).quantize(Decimal("0.01"))
    return amount


def parse_salary_text(text: str | None, *, currency: str | None = None, period: str | None = None) -> SalarySnapshot:
    if not text or not str(text).strip():
        return SalarySnapshot(published=False)
    raw = str(text).strip()
    notes: list[str] = []
    lowered = raw.lower()
    if any(token in lowered for token in ("glassdoor", "estimated", "estimate", "typically pays", "average salary")):
        notes.append("ignored_third_party_estimate")
        return SalarySnapshot(published=False, raw_text=raw, estimated=True, parse_notes=notes)

    currency_code = detect_currency(raw, currency)
    period_code = detect_period(raw, period)
    up_to = bool(re.search(r"\b(up to|upto|maximum of|max(?:imum)?)\b", lowered))
    from_only = bool(re.search(r"\b(from|starting at|minimum of|min(?:imum)?)\b", lowered) and not up_to)
    if "total compensation" in lowered or "ote" in lowered or "on-target" in lowered:
        notes.append("may_include_variable_pay")

    numbers = [_to_decimal(match.group(0)) for match in re.finditer(_NUMBER, raw)]
    numbers = [n for n in numbers if n is not None and n > 0]
    if not numbers:
        return SalarySnapshot(published=False, raw_text=raw, parse_notes=["no_numeric_salary"])

    min_amount: Decimal | None
    max_amount: Decimal | None
    if len(numbers) == 1:
        if up_to:
            min_amount, max_amount = None, numbers[0]
            notes.append("up_to_has_no_lower_bound")
        elif from_only:
            min_amount, max_amount = numbers[0], None
        else:
            min_amount = max_amount = numbers[0]
    else:
        min_amount, max_amount = min(numbers[0], numbers[1]), max(numbers[0], numbers[1])
        if up_to and not re.search(_RANGE_SEP, raw):
            min_amount, max_amount = None, numbers[0]
            notes.append("up_to_has_no_lower_bound")

    snapshot = SalarySnapshot(
        published=True,
        raw_text=raw,
        min_amount=min_amount,
        max_amount=max_amount,
        currency=currency_code,
        period=period_code,
        parse_notes=notes,
    )
    if min_amount is not None:
        snapshot.min_monthly = to_monthly(min_amount, period_code)
    if max_amount is not None:
        snapshot.max_monthly = to_monthly(max_amount, period_code)
    return snapshot


def merge_structured_salary(
    *,
    text: str | None,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
    currency: str | None,
    period: str | None,
) -> SalarySnapshot:
    if min_amount is None and max_amount is None:
        return parse_salary_text(text, currency=currency, period=period)
    period_code = detect_period(text or period or "annual", period)
    currency_code = detect_currency(text or "", currency)
    snapshot = SalarySnapshot(
        published=True,
        raw_text=text,
        min_amount=min_amount,
        max_amount=max_amount,
        currency=currency_code,
        period=period_code,
    )
    if min_amount is not None:
        snapshot.min_monthly = to_monthly(min_amount, period_code)
    if max_amount is not None:
        snapshot.max_monthly = to_monthly(max_amount, period_code)
    if min_amount is None and max_amount is not None:
        snapshot.parse_notes.append("up_to_has_no_lower_bound")
    return snapshot


def lower_bound_monthly(snapshot: SalarySnapshot) -> Decimal | None:
    if snapshot.min_monthly is not None:
        return snapshot.min_monthly
    return None
