"""Household-level orchestration: documents -> calc -> readiness -> submission.

The submission dict conforms to starter/schemas/submission.schema.json and
never contains an eligibility conclusion.
"""
from __future__ import annotations

from typing import Optional

from .calc.engine import calculate_household
from .models import CalcResult, DocumentExtraction, ReadinessResult
from .readiness.engine import assess_readiness
from .rules.corpus import MTSP, threshold_lookup


def household_size_from_documents(documents: list[DocumentExtraction]) -> Optional[int]:
    for doc in documents:
        if doc.document_type == "application_summary":
            fv = doc.get("household_size")
            if fv is not None and fv.value is not None:
                try:
                    return int(fv.value)
                except (TypeError, ValueError):
                    return None
    return None


def build_household_result(
    household_id: str,
    documents: list[DocumentExtraction],
    household_size: Optional[int] = None,
) -> tuple[CalcResult, ReadinessResult, dict]:
    if household_size is None:
        household_size = household_size_from_documents(documents)

    calc = calculate_household(household_id, household_size, documents, threshold_lookup)
    readiness = assess_readiness(household_id, documents, calc)

    citations: list[dict] = []
    for src in calc.sources:
        citations.extend(src.citations)
    if calc.threshold is not None and household_size is not None:
        row = MTSP[household_size]
        citations.append(
            {
                "rule_id": calc.threshold_rule_id,
                "effective_date": calc.threshold_effective_date,
                "source_url": calc.threshold_source_url,
                "source_locator": f"FY 2026 MTSP table, household size {household_size}, PDF page {row['source_pdf_page']}",
            }
        )
    for reason in readiness.reasons:
        citations.append({"rule_id": reason.rule_id, "reason_code": reason.code})

    submission = {
        "household_id": household_id,
        "annualized_income": calc.annualized_income,
        "comparison": calc.comparison,
        "readiness_status": readiness.readiness_status,
        "review_reasons": [
            {"code": r.code, "detail": r.detail, "rule_id": r.rule_id} for r in readiness.reasons
        ],
        "citations": citations,
        "decision_boundary": "No eligibility determination is included.",
    }
    return calc, readiness, submission
