"""Deterministic income model — no ML anywhere in this module.

Conventions (validated against the pack's gold checklists):
- One wage source per employer: use the LATEST pay stub by pay_date; stubs are
  consecutive pay periods of the same job and are never summed together.
- Recomputed components (hours x rate) are authoritative; a displayed gross
  that disagrees is flagged as PAY_STUB_TOTAL_CONFLICT and the component value
  is used (per CH-INCOME-001: sum *documented* recurring gross income).
- Benefit letters contribute monthly_benefit annualized at their stated frequency.
- Gig statements contribute gross_receipts as a monthly recurring amount
  (statement_month granularity); platform fees are not deducted (gross income).
- Employment letters corroborate wages; they never add income.
- Application-summary self-declared amounts are never income evidence
  (unsigned-claim rule, ADV-012).
"""
from __future__ import annotations

from typing import Optional

from ..config import GIG_CORROBORATION_TYPES
from ..models import CalcResult, DocumentExtraction, FieldValue, IncomeSource
from .starter_calculate import FREQUENCY, annualize, compare_to_threshold

CONFLICT_TOLERANCE = 0.01


def _usable(fv: Optional[FieldValue]) -> bool:
    return fv is not None and fv.value is not None and fv.status != "abstained"


def _wage_source(stub: DocumentExtraction) -> tuple[Optional[IncomeSource], bool]:
    """Build a wage source from one pay stub. Returns (source, conflict_detected)."""
    freq = stub.get("pay_frequency")
    gross = stub.get("gross_pay")
    hours = stub.get("regular_hours")
    rate = stub.get("hourly_rate")
    ot_hours = stub.get("overtime_hours")
    ot_rate = stub.get("overtime_rate")

    if not _usable(freq):
        return None, False
    frequency = str(freq.value).lower()
    if frequency not in FREQUENCY:
        return None, False

    component_total = None
    citations = [freq.citation()]
    formula_parts = []
    if _usable(hours) and _usable(rate):
        component_total = round(float(hours.value) * float(rate.value), 2)
        citations += [hours.citation(), rate.citation()]
        formula_parts.append(f"{hours.value} h x ${float(rate.value):.2f}/h")
        if _usable(ot_hours) and _usable(ot_rate):
            component_total = round(component_total + float(ot_hours.value) * float(ot_rate.value), 2)
            citations += [ot_hours.citation(), ot_rate.citation()]
            formula_parts.append(f"+ {ot_hours.value} OT h x ${float(ot_rate.value):.2f}/h")

    displayed = float(gross.value) if _usable(gross) else None
    conflict = (
        component_total is not None
        and displayed is not None
        and abs(component_total - displayed) > CONFLICT_TOLERANCE
    )

    if component_total is not None:
        amount = component_total
    elif displayed is not None:
        amount = displayed
        citations.append(gross.citation())
        formula_parts.append(f"documented gross ${displayed:.2f}")
    else:
        return None, False

    if not conflict and displayed is not None and gross is not None:
        citations.append(gross.citation())

    annual = annualize(amount, frequency)
    formula = f"({' '.join(formula_parts) or f'${amount:.2f}'}) = ${amount:.2f} {frequency} x {FREQUENCY[frequency]} = ${annual:,.2f}/yr"
    flags = ["PAY_STUB_TOTAL_CONFLICT"] if conflict else []
    if conflict:
        formula += (
            f" [displayed gross ${displayed:.2f} conflicts with computed components"
            f" ${component_total:.2f}; component value used]"
        )
    return (
        IncomeSource(
            source_type="wages",
            document_id=stub.document_id,
            amount=amount,
            frequency=frequency,
            annualized=annual,
            formula=formula,
            citations=citations,
            flags=flags,
        ),
        conflict,
    )


def build_income_sources(documents: list[DocumentExtraction]) -> list[IncomeSource]:
    sources: list[IncomeSource] = []

    # Wages: latest pay stub only (consecutive periods, same employer).
    stubs = [d for d in documents if d.document_type == "pay_stub"]

    def stub_date(d: DocumentExtraction) -> str:
        fv = d.get("pay_date")
        return str(fv.value) if _usable(fv) else ""

    stubs.sort(key=stub_date, reverse=True)
    conflict_anywhere = any(_wage_source(s)[1] for s in stubs)
    for stub in stubs:  # newest first; fall back if a stub lacks usable fields
        src, _ = _wage_source(stub)
        if src is not None:
            if conflict_anywhere and "PAY_STUB_TOTAL_CONFLICT" not in src.flags:
                src.flags.append("PAY_STUB_TOTAL_CONFLICT")
            sources.append(src)
            break

    # Benefits: monthly_benefit at stated frequency.
    for doc in documents:
        if doc.document_type != "benefit_letter":
            continue
        amount = doc.get("monthly_benefit")
        freq = doc.get("benefit_frequency")
        if not _usable(amount):
            continue
        frequency = str(freq.value).lower() if _usable(freq) else "monthly"
        if frequency not in FREQUENCY:
            frequency = "monthly"
        annual = annualize(float(amount.value), frequency)
        citations = [amount.citation()] + ([freq.citation()] if _usable(freq) else [])
        sources.append(
            IncomeSource(
                source_type="benefit",
                document_id=doc.document_id,
                amount=float(amount.value),
                frequency=frequency,
                annualized=annual,
                formula=f"${float(amount.value):,.2f} {frequency} x {FREQUENCY[frequency]} = ${annual:,.2f}/yr",
                citations=citations,
            )
        )

    # Gig: gross_receipts as monthly recurring; corroboration checked elsewhere.
    present_types = {d.document_type for d in documents}
    for doc in documents:
        if doc.document_type != "gig_statement":
            continue
        receipts = doc.get("gross_receipts")
        if not _usable(receipts):
            continue
        annual = annualize(float(receipts.value), "monthly")
        flags = []
        if not (present_types & GIG_CORROBORATION_TYPES):
            flags.append("GIG_INCOME_UNCORROBORATED")
        sources.append(
            IncomeSource(
                source_type="gig",
                document_id=doc.document_id,
                amount=float(receipts.value),
                frequency="monthly",
                annualized=annual,
                formula=f"${float(receipts.value):,.2f} gross receipts/month x 12 = ${annual:,.2f}/yr",
                citations=[receipts.citation()],
                flags=flags,
            )
        )

    return sources


def calculate_household(
    household_id: str,
    household_size: Optional[int],
    documents: list[DocumentExtraction],
    threshold_lookup,
) -> CalcResult:
    """threshold_lookup(size) -> (threshold, rule_id, effective_date, source_url) or None."""
    sources = build_income_sources(documents)
    total = round(sum(s.annualized for s in sources), 2)

    threshold = rule_id = eff = url = None
    if household_size is not None:
        row = threshold_lookup(household_size)
        if row is not None:
            threshold, rule_id, eff, url = row

    if threshold is None:
        comparison = "no_frozen_threshold"
    else:
        comparison = compare_to_threshold(total, threshold)

    formula = " + ".join(f"${s.annualized:,.2f} ({s.source_type})" for s in sources)
    formula = f"{formula or '$0.00'} = ${total:,.2f}/yr vs 60% MTSP ${threshold:,.2f}" if threshold else f"{formula or '$0.00'} = ${total:,.2f}/yr (no frozen threshold for household size {household_size})"

    return CalcResult(
        household_id=household_id,
        household_size=household_size,
        sources=sources,
        annualized_income=total,
        threshold=threshold,
        comparison=comparison,
        threshold_rule_id=rule_id,
        threshold_effective_date=eff,
        threshold_source_url=url,
        formula=formula,
    )
