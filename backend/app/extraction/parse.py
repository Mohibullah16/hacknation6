"""Deterministic value normalization for extracted field text.

Each parser returns (value, ok). `ok=False` means the raw text did not match
the expected shape — the field is then abstained, never guessed.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_MONEY = re.compile(r"^\$?\s*([\d,]+(?:\.\d{1,2})?)$")
_NUMBER = re.compile(r"^([\d,]+(?:\.\d+)?)$")
_INT = re.compile(r"^(\d{1,2})$")
_FREQ = {"weekly", "biweekly", "semimonthly", "monthly", "annual"}


def _clean(text: str) -> str:
    return text.strip().strip(",;")


def parse_date(text: str):
    t = _clean(text)
    return (t, True) if _DATE.match(t) else (t, False)


def parse_month(text: str):
    t = _clean(text)
    return (t, True) if _MONTH.match(t) else (t, False)


def parse_money(text: str):
    m = _MONEY.match(_clean(text))
    if not m:
        return None, False
    value = float(m.group(1).replace(",", ""))
    return (int(value) if value == int(value) else value), True


def parse_number(text: str):
    m = _NUMBER.match(_clean(text))
    if not m:
        return None, False
    value = float(m.group(1).replace(",", ""))
    return (int(value) if value == int(value) else value), True


def parse_int(text: str):
    m = _INT.match(_clean(text))
    return (int(m.group(1)), True) if m else (None, False)


def parse_frequency(text: str):
    t = _clean(text).lower()
    return (t, t in _FREQ)


def parse_text(text: str):
    t = _clean(text)
    return (t, bool(t))


def parse_person_name(text: str):
    """OCR may collapse the space in 'Jonas Vale' -> 'JonasVale'; re-space at
    lower->Upper boundaries (idempotent on clean text)."""
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", _clean(text))
    return (t, bool(t))


def parse_address(text: str):
    """Re-space OCR-collapsed addresses: commas, camel-case, letter/digit
    boundaries ('81PaperMillRoad,Cambridge,MA02139' -> proper spacing)."""
    t = _clean(text)
    t = re.sub(r",(?=\S)", ", ", t)
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)
    t = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", t)
    t = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return (t, bool(t))


PARSERS: dict[str, Callable[[str], tuple[Any, bool]]] = {
    "person_name": parse_person_name,
    "address": parse_address,
    "household_size": parse_int,
    "application_date": parse_date,
    "pay_date": parse_date,
    "pay_period_start": parse_date,
    "pay_period_end": parse_date,
    "document_date": parse_date,
    "statement_month": parse_month,
    "pay_frequency": parse_frequency,
    "benefit_frequency": parse_frequency,
    "regular_hours": parse_number,
    "overtime_hours": parse_number,
    "weekly_hours": parse_number,
    "hourly_rate": parse_money,
    "overtime_rate": parse_money,
    "gross_pay": parse_money,
    "net_pay": parse_money,
    "monthly_benefit": parse_money,
    "gross_receipts": parse_money,
    "platform_fees": parse_money,
}


def parse_field(field: str, text: str) -> tuple[Any, bool]:
    parser = PARSERS.get(field, parse_text)
    return parser(text)
