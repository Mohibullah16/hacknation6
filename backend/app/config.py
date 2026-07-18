"""Frozen challenge configuration. Every constant here is a challenge convention
or an official frozen value from the organizer pack — nothing is inferred at runtime."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PACK_DATA = BACKEND_DIR / "pack_data"

DOCUMENTS_DIR = PACK_DATA / "synthetic_documents" / "documents"
GOLD_DIR = PACK_DATA / "synthetic_documents" / "gold"
RULE_CORPUS_PATH = PACK_DATA / "rules" / "rule_corpus.jsonl"
MTSP_CSV_PATH = PACK_DATA / "data" / "mtsp_2026_boston_cambridge_quincy.csv"
LIHTC_CSV_PATH = PACK_DATA / "data" / "lihtc_boston_metro_subset.csv"
CHECKLISTS_PATH = PACK_DATA / "evaluation" / "application_checklists.json"
SUBMISSION_SCHEMA_PATH = PACK_DATA / "schemas" / "submission.schema.json"

# Challenge convention (CH-READINESS-001): evidence dated within 60 days of the
# frozen event date is current. This is NOT a universal LIHTC rule.
EVENT_DATE = date(2026, 7, 18)
CURRENCY_WINDOW_DAYS = 60
CURRENCY_CUTOFF = EVENT_DATE - timedelta(days=CURRENCY_WINDOW_DAYS)

RULE_CORPUS_VERSION = "frozen-2026-07-18"

PAGE_WIDTH_PT = 612.0
PAGE_HEIGHT_PT = 792.0

# Field allowlist (privacy requirement): only these fields may ever be
# extracted, stored, or displayed. Derived from the pack field schema/gold.
FIELD_ALLOWLIST = {
    "person_name",
    "household_size",
    "address",
    "application_date",
    "pay_date",
    "pay_period_start",
    "pay_period_end",
    "pay_frequency",
    "regular_hours",
    "overtime_hours",
    "hourly_rate",
    "overtime_rate",
    "gross_pay",
    "net_pay",
    "document_date",
    "weekly_hours",
    "monthly_benefit",
    "benefit_frequency",
    "statement_month",
    "gross_receipts",
    "platform_fees",
}

DOCUMENT_TYPES = {
    "application_summary",
    "pay_stub",
    "employment_letter",
    "benefit_letter",
    "gig_statement",
}

# Document types that corroborate gig income (challenge checklist convention).
GIG_CORROBORATION_TYPES = {"gig_income_corroboration"}

# Confidence below this forces abstention: the value is withheld and the renter
# must enter/confirm it manually.
ABSTAIN_CONFIDENCE = 0.60
