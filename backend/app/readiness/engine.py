"""Document-readiness reason engine.

Calibrated against the pack's gold checklists:
- NEEDS_REVIEW is driven ONLY by explicit reason codes (conflicts, expiry,
  uncorroborated gig income, out-of-table household size, missing citations).
- Missing required documents are surfaced as informational checklist gaps —
  gold shows households missing an employment letter can still be
  READY_TO_REVIEW when pay stubs are current and internally consistent.
- Never produces an eligibility conclusion; READY_TO_REVIEW means "a qualified
  human can review this packet now".
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from ..config import CURRENCY_CUTOFF, CURRENCY_WINDOW_DAYS, EVENT_DATE
from ..models import CalcResult, DocumentExtraction, ReadinessReason, ReadinessResult

# Required docs per scenario are session-specific; the general convention from
# the pack checklists: application summary + pay stub + employment letter, plus
# benefit letter when benefits are claimed, plus corroboration when gig income
# is claimed.
BASE_REQUIRED = ["application_summary", "pay_stub", "employment_letter"]

DATE_FIELDS_BY_TYPE = {
    "employment_letter": "document_date",
    "benefit_letter": "document_date",
    "pay_stub": "pay_date",
    "application_summary": "application_date",
    "gig_statement": "statement_month",
}


def _parse_date(value) -> Optional[date]:
    s = str(value)
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _doc_date(doc: DocumentExtraction) -> Optional[date]:
    field_name = DATE_FIELDS_BY_TYPE.get(doc.document_type)
    if field_name is None:
        return None
    fv = doc.get(field_name)
    if fv is None or fv.value is None:
        return None
    return _parse_date(fv.value)


def required_documents(documents: list[DocumentExtraction]) -> list[str]:
    required = list(BASE_REQUIRED)
    types = {d.document_type for d in documents}
    if "benefit_letter" in types:
        required.append("benefit_letter")
    if "gig_statement" in types:
        required.append("gig_income_corroboration")
    return required


def assess_readiness(
    household_id: str,
    documents: list[DocumentExtraction],
    calc: CalcResult,
) -> ReadinessResult:
    reasons: list[ReadinessReason] = []
    gaps: list[dict] = []

    present_types = {d.document_type for d in documents}
    required = required_documents(documents)

    # Informational gaps (do not flip status by themselves).
    for req in required:
        if req not in present_types:
            gaps.append(
                {
                    "document_type": req,
                    "status": "missing",
                    "guidance": _gap_guidance(req),
                }
            )

    # 1. Pay component / displayed-gross conflicts (from calc engine flags).
    for src in calc.sources:
        if "PAY_STUB_TOTAL_CONFLICT" in src.flags:
            reasons.append(
                ReadinessReason(
                    code="PAY_STUB_TOTAL_CONFLICT",
                    detail=(
                        "A pay stub's displayed gross does not reconcile with its "
                        "documented components (hours x rate). A human reviewer must "
                        "resolve the discrepancy."
                    ),
                    rule_id="CH-READINESS-001",
                    citations=src.citations,
                )
            )
            break

    # 2. Expired evidence (challenge 60-day convention).
    for doc in documents:
        d = _doc_date(doc)
        if d is not None and d < CURRENCY_CUTOFF:
            reasons.append(
                ReadinessReason(
                    code=f"{doc.document_type.upper()}_EXPIRED",
                    detail=(
                        f"{doc.document_type.replace('_', ' ')} dated {d.isoformat()} is older "
                        f"than the {CURRENCY_WINDOW_DAYS}-day currency convention "
                        f"(cutoff {CURRENCY_CUTOFF.isoformat()} for event date {EVENT_DATE.isoformat()}). "
                        "This convention is simulation-specific, not a universal LIHTC rule."
                    ),
                    rule_id="CH-READINESS-001",
                    citations=[fv.citation() for fv in doc.fields if fv.field == DATE_FIELDS_BY_TYPE.get(doc.document_type)],
                )
            )
            gaps.append(
                {
                    "document_type": doc.document_type,
                    "status": "expired",
                    "guidance": f"Request an updated {doc.document_type.replace('_', ' ')} dated after {CURRENCY_CUTOFF.isoformat()}.",
                }
            )

    # 3. Uncorroborated gig income.
    for src in calc.sources:
        if "GIG_INCOME_UNCORROBORATED" in src.flags:
            reasons.append(
                ReadinessReason(
                    code="GIG_INCOME_UNCORROBORATED",
                    detail=(
                        "Gig income is documented by a platform statement only; the "
                        "checklist requires independent corroboration before review."
                    ),
                    rule_id="CH-INCOME-001",
                    citations=src.citations,
                )
            )
            break

    # 4. Household size outside frozen table.
    if calc.comparison == "no_frozen_threshold":
        reasons.append(
            ReadinessReason(
                code="HOUSEHOLD_SIZE_OUT_OF_TABLE",
                detail=(
                    f"Household size {calc.household_size} is outside the frozen 1-8 "
                    "MTSP table; no frozen threshold exists, so a human must apply "
                    "the program's own procedures."
                ),
                rule_id="CH-READINESS-001",
            )
        )

    # 5. No documented income evidence at all.
    if not calc.sources:
        reasons.append(
            ReadinessReason(
                code="NO_INCOME_EVIDENCE",
                detail=(
                    "No usable income evidence was documented (self-declared "
                    "application amounts are not evidence)."
                ),
                rule_id="CH-INCOME-001",
            )
        )

    # 5b. Traceability gate: every income source must be fully cited.
    for src in calc.sources:
        missing = [c for c in src.citations if not c.get("bbox") or c.get("page") is None]
        if missing or not src.citations:
            reasons.append(
                ReadinessReason(
                    code="MISSING_CITATION",
                    detail=(
                        f"The {src.source_type} income source lacks a complete page/source-box "
                        "citation; uncited values cannot be marked ready."
                    ),
                    rule_id="CH-READINESS-001",
                )
            )
            break

    # 6. Unconfirmed or abstained material fields.
    unconfirmed = []
    for doc in documents:
        for fv in doc.fields:
            if fv.status == "abstained":
                unconfirmed.append(f"{doc.document_id}:{fv.field}")
    if unconfirmed:
        reasons.append(
            ReadinessReason(
                code="UNCONFIRMED_EVIDENCE",
                detail=(
                    "Some extracted values were abstained (low confidence) and have not "
                    "been confirmed or corrected: " + ", ".join(unconfirmed[:6])
                ),
                rule_id="CH-READINESS-001",
            )
        )

    status = "READY_TO_REVIEW" if not reasons else "NEEDS_REVIEW"
    return ReadinessResult(
        household_id=household_id,
        readiness_status=status,
        reasons=reasons,
        checklist_gaps=gaps,
    )


def _gap_guidance(doc_type: str) -> str:
    return {
        "employment_letter": "Ask your employer for a signed letter stating role, hours, and rate (dated within 60 days).",
        "pay_stub": "Add your most recent pay stub showing pay period, hours, rate, and gross pay.",
        "application_summary": "Complete the program's application summary form.",
        "benefit_letter": "Request a current benefit award letter from the issuing agency.",
        "gig_income_corroboration": "Add independent corroboration for gig income (e.g., bank deposits or platform annual summary).",
    }.get(doc_type, "Provide this document to complete the packet.")
