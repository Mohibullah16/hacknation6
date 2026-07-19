"""Data model for extracted evidence, calculations, and readiness results.

Everything material carries a citation (document_id, page, bbox) or a rule_id.
No model in this file can represent an eligibility decision — by design.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class FieldValue:
    field: str
    value: Any                      # None when abstained
    page: Optional[int]
    bbox: Optional[list[float]]     # [x1, y1, x2, y2] PDF points, bottom-left origin
    bbox_units: str = "pdf_points_bottom_left_origin"
    confidence: float = 0.0
    status: str = "extracted"       # extracted | abstained | confirmed | corrected
    document_id: str = ""

    def citation(self) -> dict:
        return {
            "document_id": self.document_id,
            "page": self.page,
            "bbox": self.bbox,
            "bbox_units": self.bbox_units,
            "field": self.field,
        }


@dataclass
class DocumentExtraction:
    document_id: str
    household_id: str
    document_type: str
    file_name: str
    rasterized: bool
    fields: list[FieldValue] = field(default_factory=list)
    adversarial_text_detected: bool = False
    adversarial_note: str = ""
    # Optional LLM cross-check output (opt-in): advisory "double-check this
    # value" notes only — never authoritative, never used in any computation.
    advisory_flags: list[dict] = field(default_factory=list)

    def get(self, name: str) -> Optional[FieldValue]:
        for f in self.fields:
            if f.field == name:
                return f
        return None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IncomeSource:
    source_type: str                # wages | benefit | gig
    document_id: str
    amount: float                   # per-period gross amount used
    frequency: str                  # weekly | biweekly | semimonthly | monthly | annual
    annualized: float
    formula: str
    citations: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


@dataclass
class CalcResult:
    household_id: str
    household_size: Optional[int]
    sources: list[IncomeSource]
    annualized_income: float
    threshold: Optional[float]
    comparison: str                 # below_or_equal | above | no_frozen_threshold
    threshold_rule_id: Optional[str]
    threshold_effective_date: Optional[str]
    threshold_source_url: Optional[str]
    formula: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReadinessReason:
    code: str
    detail: str
    rule_id: str
    citations: list[dict] = field(default_factory=list)


@dataclass
class ReadinessResult:
    household_id: str
    readiness_status: str           # READY_TO_REVIEW | NEEDS_REVIEW
    reasons: list[ReadinessReason] = field(default_factory=list)
    checklist_gaps: list[dict] = field(default_factory=list)  # informational, not status-driving

    def to_dict(self) -> dict:
        return asdict(self)
