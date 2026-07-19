"""Frozen challenge configuration. Every constant here is a challenge convention
or an official frozen value from the organizer pack — nothing is inferred at
runtime. The only environment-driven values are the optional LLM-assist flags
at the bottom, which can never affect a scored number."""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PACK_DATA = BACKEND_DIR / "pack_data"

# Load backend/.env if present (gitignored) so the OpenAI key doesn't have to
# be exported per-terminal. Real environment variables win over the file.
try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:  # optional dependency — fine to run without it
    pass

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

# ---------------------------------------------------------------------------
# Optional OpenAI assist (non-authoritative; disclosed at the consent screen).
# With no OPENAI_API_KEY the app is fully local and deterministic — the scored
# engines never depend on these flags. The assist may only (a) route a free-
# text question to a vetted template intent, (b) add a gated plain-language
# rephrasing beside the deterministic cited answer, and (c) when the opt-in
# cross-check flag is on, add advisory "double-check this value" notes that the
# renter still confirms. It can never produce a number, status, or decision.
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
LLM_ASSIST_ENABLED = bool(OPENAI_API_KEY) and os.environ.get("REALDOOR_LLM_ASSIST", "1") != "0"
LLM_EXPLAIN_ENABLED = LLM_ASSIST_ENABLED and os.environ.get("REALDOOR_LLM_EXPLAIN", "1") != "0"
# Cross-check is opt-in (off by default) so the default posture sends nothing
# to OpenAI except the renter's typed question.
LLM_CROSSCHECK_ENABLED = LLM_ASSIST_ENABLED and os.environ.get("REALDOOR_LLM_CROSSCHECK", "0") == "1"
LLM_TIMEOUT_SECONDS = 12.0
