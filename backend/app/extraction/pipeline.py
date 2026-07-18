"""Document extraction pipeline: route text-layer vs OCR, label fields,
normalize values, attach confidence, detect adversarial content, and enforce
the field allowlist and bbox validity.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..config import ABSTAIN_CONFIDENCE, FIELD_ALLOWLIST
from ..models import DocumentExtraction, FieldValue
from ..safety.guards import detect_injection, validate_bbox
from .labeling import detect_document_type, extract_labeled_values
from .ocr import extract_tokens_ocr
from .parse import parse_field
from .textlayer import extract_tokens, has_text_layer

_DOC_ID = re.compile(r"\b(HH-\d{3})-D(\d{2})\b", re.I)

TEXT_LAYER_CONFIDENCE = 0.97
OCR_BASE_CONFIDENCE = 0.85


def extract_document(pdf_path: str | Path, fallback_document_id: str = "") -> DocumentExtraction:
    pdf_path = Path(pdf_path)

    if has_text_layer(pdf_path):
        tokens, full_text, width, height = extract_tokens(pdf_path)
        rasterized = False
        base_conf = TEXT_LAYER_CONFIDENCE
    else:
        tokens, full_text, width, height, ocr_score = extract_tokens_ocr(pdf_path)
        rasterized = True
        base_conf = min(OCR_BASE_CONFIDENCE, max(0.0, ocr_score))

    # Identify document
    m = _DOC_ID.search(full_text)
    if m:
        household_id = m.group(1).upper()
        document_id = f"{household_id}-D{m.group(2)}"
    else:
        document_id = fallback_document_id or pdf_path.stem
        hm = re.search(r"hh-?(\d{3})", pdf_path.stem, re.I)
        household_id = f"HH-{hm.group(1)}" if hm else ""

    doc_type = detect_document_type(tokens) or _type_from_name(pdf_path.stem) or "unknown"

    # Untrusted-content firewall: detect embedded instructions; they are never
    # extracted as fields and never influence behavior.
    injections = detect_injection(full_text)

    doc = DocumentExtraction(
        document_id=document_id,
        household_id=household_id,
        document_type=doc_type,
        file_name=pdf_path.name,
        rasterized=rasterized,
        adversarial_text_detected=bool(injections),
        adversarial_note=(
            "Instruction-like text was found inside this document. It was treated as "
            "untrusted data and ignored: " + "; ".join(f"“{s}”" for s in injections)
            if injections
            else ""
        ),
    )

    if doc_type not in ("unknown",) and doc_type in _label_specs():
        raw = extract_labeled_values(tokens, doc_type)
        for field_name, item in raw.items():
            if field_name not in FIELD_ALLOWLIST:
                continue
            value, ok = parse_field(field_name, item["text"])
            bbox_ok = validate_bbox(item["bbox"], width, height)
            confidence = base_conf if ok else base_conf * 0.5
            if not bbox_ok:
                confidence = 0.0
            abstain = (not ok) or (not bbox_ok) or confidence < ABSTAIN_CONFIDENCE
            doc.fields.append(
                FieldValue(
                    field=field_name,
                    value=None if abstain else value,
                    page=1,
                    bbox=item["bbox"] if bbox_ok else None,
                    confidence=round(confidence, 3),
                    status="abstained" if abstain else "extracted",
                    document_id=document_id,
                )
            )
    return doc


def _type_from_name(stem: str) -> Optional[str]:
    for t in ("application_summary", "pay_stub", "employment_letter", "benefit_letter", "gig_statement"):
        if t in stem:
            return t
    return None


def _label_specs():
    from .labeling import LABEL_SPECS

    return LABEL_SPECS
