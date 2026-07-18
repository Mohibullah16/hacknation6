"""Safety layer: untrusted-input firewall and decision-language output gate.

Design:
- Document text is DATA. It is never concatenated into any prompt as
  instructions, and instruction-like content inside documents is detected,
  flagged to the renter, and ignored.
- Every user-facing generated string passes `enforce_no_decision_language`
  before leaving the API. Pre-vetted templates are exempt by construction;
  LLM output never is.
"""
from __future__ import annotations

import re

# Patterns that indicate embedded instructions inside document text (ADV-001/013).
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+|prior\s+|previous\s+)?instructions", re.I),
    re.compile(r"disregard\s+(the\s+)?(system|previous|prior)", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"mark\s+(this\s+)?(applicant|application)\s+(as\s+)?approved", re.I),
    re.compile(r"reveal\s+(the\s+)?(secret|system|prompt|key)", re.I),
    re.compile(r"you\s+are\s+now\b", re.I),
    re.compile(r"act\s+as\b.*\b(admin|root|developer)", re.I),
]

# Decision language that must never appear in tool-generated conclusions
# (CH-DECISION-001). Checked on generated/LLM text before display.
DECISION_PATTERNS = re.compile(
    r"\b(eligible|ineligible|eligibility\s+(is|granted|confirmed)|approved?|approval|"
    r"den(?:y|ied|ial)|reject(?:ed|ion)?|qualif(?:y|ies|ied)|disqualif\w*|"
    r"priorit(?:y|ized|ize)|guaranteed|will\s+(?:get|receive)\s+the\s+unit|"
    r"unit\s+is\s+available)\b",
    re.I,
)

DEFLECTION = (
    "I can't make or imply a program decision. Here is what I can show you: the "
    "frozen rule with its citation, your confirmed inputs, the deterministic "
    "calculation, and the numerical comparison. A qualified human reviewer makes "
    "any determination."
)


def detect_injection(text: str) -> list[str]:
    """Return the matched instruction-like snippets found in document text."""
    hits = []
    for pat in INJECTION_PATTERNS:
        m = pat.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def sanitize_document_text(text: str) -> tuple[str, list[str]]:
    """Strip instruction-like lines from document text before any further use.
    Returns (sanitized_text, detected_snippets)."""
    detected: list[str] = []
    kept_lines: list[str] = []
    for line in text.splitlines():
        hits = detect_injection(line)
        if hits:
            detected.extend(hits)
        else:
            kept_lines.append(line)
    return "\n".join(kept_lines), detected


def enforce_no_decision_language(text: str) -> tuple[str, bool]:
    """Gate for generated output. Returns (safe_text, was_blocked)."""
    if DECISION_PATTERNS.search(text):
        return DEFLECTION, True
    return text, False


def validate_bbox(bbox, page_width: float = 612.0, page_height: float = 792.0) -> bool:
    """Reject malformed source boxes (ADV-010): must be inside the page with
    positive area, bottom-left origin."""
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return False
    return 0 <= x1 < x2 <= page_width and 0 <= y1 < y2 <= page_height
