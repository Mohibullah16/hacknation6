"""Label-anchor field extraction shared by the text-layer and OCR paths.

Documents are simple one-page forms: an UPPERCASE label row with the value
printed directly beneath each label. We locate label phrases and capture the
value tokens in the band below, bounded on the right by the next label column.

Tokens are dicts: {text, x0, x1, y0, y1} in PDF points, bottom-left origin.
"""
from __future__ import annotations

from typing import Optional

LINE_TOL = 4.0          # tokens within this y-distance form one line
VALUE_BAND = 26.0       # value line must start within this many points below label
COL_SLACK = 6.0         # value may start slightly left of its label column

# Per document type: list of (label word tuple, field name).
# Longest phrases are matched first so "PAY FREQUENCY" beats "PAY".
LABEL_SPECS: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "application_summary": [
        (("MAILING", "ADDRESS"), "address"),
        (("APPLICATION", "DATE"), "application_date"),
        (("HOUSEHOLD", "SIZE"), "household_size"),
        (("APPLICANT",), "person_name"),
    ],
    "pay_stub": [
        (("PAY", "FREQUENCY"), "pay_frequency"),
        (("REGULAR", "HOURS"), "regular_hours"),
        (("OVERTIME", "HOURS"), "overtime_hours"),
        (("OVERTIME", "RATE"), "overtime_rate"),
        (("HOURLY", "RATE"), "hourly_rate"),
        (("GROSS", "PAY"), "gross_pay"),
        (("NET", "PAY"), "net_pay"),
        (("PAY", "PERIOD"), "pay_period_start"),
        (("THROUGH",), "pay_period_end"),
        (("PAY", "DATE"), "pay_date"),
        (("EMPLOYEE",), "person_name"),
    ],
    "employment_letter": [
        (("HOURS", "PER", "WEEK"), "weekly_hours"),
        (("HOURLY", "RATE"), "hourly_rate"),
        (("LETTER", "DATE"), "document_date"),
        (("EMPLOYEE",), "person_name"),
    ],
    "benefit_letter": [
        (("MONTHLY", "AMOUNT"), "monthly_benefit"),
        (("LETTER", "DATE"), "document_date"),
        (("FREQUENCY",), "benefit_frequency"),
        (("RECIPIENT",), "person_name"),
    ],
    "gig_statement": [
        (("STATEMENT", "MONTH"), "statement_month"),
        (("GROSS", "RECEIPTS"), "gross_receipts"),
        (("PLATFORM", "FEES"), "platform_fees"),
        (("WORKER",), "person_name"),
    ],
}

TITLE_TO_TYPE = {
    "application summary": "application_summary",
    "pay stub": "pay_stub",
    "employment letter": "employment_letter",
    "benefit letter": "benefit_letter",
    "gig statement": "gig_statement",
}


def group_lines(tokens: list[dict]) -> list[list[dict]]:
    """Group tokens into lines by vertical position (descending y = top first)."""
    lines: list[list[dict]] = []
    for tok in sorted(tokens, key=lambda t: (-t["y1"], t["x0"])):
        placed = False
        for line in lines:
            if abs(line[0]["y1"] - tok["y1"]) <= LINE_TOL:
                line.append(tok)
                placed = True
                break
        if not placed:
            lines.append([tok])
    for line in lines:
        line.sort(key=lambda t: t["x0"])
    return lines


def detect_document_type(tokens: list[dict]) -> Optional[str]:
    joined = " ".join(t["text"] for t in tokens).lower()
    for title, doc_type in TITLE_TO_TYPE.items():
        if title in joined:
            return doc_type
    return None


def _match_phrase_run(words: list[str], start: int, concat: str) -> Optional[int]:
    """Match a label phrase against a run of tokens whose concatenation equals
    the phrase (OCR may merge label words: 'PAYPERIOD', 'HOURSPERWEEK')."""
    acc = ""
    j = start
    while j < len(words):
        acc += words[j]
        if acc == concat:
            return j
        if not concat.startswith(acc):
            return None
        j += 1
    return None


def _find_label_positions(lines: list[list[dict]], spec) -> list[dict]:
    """Find each label phrase occurrence: {field, x0, y0 (label bottom), x_next}."""
    # Longest concatenated phrase first so PAY FREQUENCY beats shorter matches.
    ordered = sorted(spec, key=lambda p: -len("".join(p[0])))
    found: list[dict] = []
    for line in lines:
        words = [t["text"].upper().rstrip(":") for t in line]
        used = [False] * len(line)
        line_hits: list[tuple[int, int, str]] = []  # (start_idx, end_idx, field)
        for phrase, fieldname in ordered:
            concat = "".join(phrase)
            for i in range(len(words)):
                if used[i]:
                    continue
                end = _match_phrase_run(words, i, concat)
                if end is not None and not any(used[i : end + 1]):
                    for k in range(i, end + 1):
                        used[k] = True
                    line_hits.append((i, end, fieldname))
                    break  # one occurrence per line per field
        # Column boundary: next label's x0 on the same line.
        line_hits.sort(key=lambda h: line[h[0]]["x0"])
        for idx, (s, e, fieldname) in enumerate(line_hits):
            x_next = line[line_hits[idx + 1][0]]["x0"] if idx + 1 < len(line_hits) else float("inf")
            found.append(
                {
                    "field": fieldname,
                    "x0": line[s]["x0"],
                    "label_y0": min(t["y0"] for t in line[s : e + 1]),
                    "x_next": x_next,
                }
            )
    return found


def extract_labeled_values(tokens: list[dict], doc_type: str) -> dict[str, dict]:
    """Returns {field: {"text": raw_value_text, "bbox": [x1,y1,x2,y2]}}."""
    spec = LABEL_SPECS[doc_type]
    lines = group_lines(tokens)
    labels = _find_label_positions(lines, spec)
    seen_fields: set[str] = set()
    out: dict[str, dict] = {}

    for lab in labels:
        if lab["field"] in seen_fields:
            continue
        # Nearest line strictly below the label within the value band.
        best_line = None
        best_gap = None
        for line in lines:
            line_top = max(t["y1"] for t in line)
            gap = lab["label_y0"] - line_top
            if 0 < gap <= VALUE_BAND:
                if best_gap is None or gap < best_gap:
                    candidate = [
                        t
                        for t in line
                        if t["x0"] >= lab["x0"] - COL_SLACK and t["x0"] < lab["x_next"] - COL_SLACK
                    ]
                    if candidate:
                        best_line, best_gap = candidate, gap
        if not best_line:
            continue
        # Trim trailing tokens separated by a large horizontal gap (column bleed).
        value_tokens = [best_line[0]]
        for tok in best_line[1:]:
            if tok["x0"] - value_tokens[-1]["x1"] > 40:
                break
            value_tokens.append(tok)
        text = " ".join(t["text"] for t in value_tokens)
        x0 = min(t["x0"] for t in value_tokens)
        y0 = min(t["y0"] for t in value_tokens)
        x1 = max(t["x1"] for t in value_tokens)
        y1 = max(t["y1"] for t in value_tokens)
        # Gold evidence boxes are padded to a minimum footprint (short numeric
        # values get a ~24pt-wide, 14pt-tall box); mirror that convention.
        x1 = max(x1, x0 + 24.0)
        y1 = max(y1, y0 + 14.0)
        out[lab["field"]] = {"text": text, "bbox": [round(v, 2) for v in (x0, y0, x1, y1)]}
        seen_fields.add(lab["field"])
    return out
