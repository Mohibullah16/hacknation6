"""Frozen rule corpus loader, MTSP threshold lookup, and citation-gated Q&A.

The Q&A engine is deterministic retrieval over the 11 frozen rules plus a set
of intent handlers for the scored question shapes. It abstains when nothing in
the frozen corpus answers the question. It never emits eligibility language —
answers are passed through the safety output validator by the API layer.
"""
from __future__ import annotations

import csv
import json
import re
from typing import Optional

from ..config import MTSP_CSV_PATH, RULE_CORPUS_PATH


def load_rules() -> dict[str, dict]:
    rules: dict[str, dict] = {}
    with RULE_CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                rules[r["rule_id"]] = r
    return rules


def load_mtsp() -> dict[int, dict]:
    table: dict[int, dict] = {}
    with MTSP_CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            table[int(row["household_size"])] = {
                "threshold_60": float(row["income_limit_60_percent"]),
                "limit_50": float(row["income_limit_50_percent"]),
                "effective_date": row["effective_date"],
                "source_url": row["source_url"],
                "source_pdf_page": row["source_pdf_page"],
                "hud_area": row["hud_area"],
            }
    return table


RULES = load_rules()
MTSP = load_mtsp()


def threshold_lookup(household_size: int):
    """Returns (threshold, rule_id, effective_date, source_url) or None if size
    is outside the frozen 1-8 table (never extrapolate)."""
    row = MTSP.get(household_size)
    if row is None:
        return None
    return row["threshold_60"], "HUD-MTSP-002", row["effective_date"], row["source_url"]


def rule_answer(rule_id: str, answer: str) -> dict:
    r = RULES[rule_id]
    return {
        "answer": answer,
        "citations": [
            {
                "rule_id": rule_id,
                "authority": r["authority"],
                "effective_date": r.get("effective_date"),
                "source_url": r["source_url"],
                "source_locator": r["source_locator"],
                "rule_text": r["text"],
            }
        ],
        "authority_label": (
            "Official source" if r["authority"].startswith("official") else "Hackathon simulation convention — not a universal rule"
        ),
        "abstained": False,
    }


ABSTAIN = {
    "answer": (
        "I can't answer that from the frozen rule corpus for this challenge. "
        "I only answer questions grounded in the versioned 2026 corpus; please "
        "consult the program's qualified staff for anything beyond it."
    ),
    "citations": [],
    "authority_label": None,
    "abstained": True,
}

_HH = re.compile(r"\bhh-?0*(\d+)\b", re.I)
_SIZE = re.compile(r"\b(?:household size|size|family of)\s+(\d+)\b", re.I)


def _match_any(q: str, *terms: str) -> bool:
    return any(t in q for t in terms)


def answer_question(question: str, session=None) -> dict:
    """Deterministic intent router. `session` (optional) provides confirmed
    household context: .household_id, .household_size, .calc (CalcResult),
    .readiness (ReadinessResult)."""
    q = question.lower().strip()

    # --- Safety-sensitive intents first ---
    if _match_any(q, "eligible", "ineligible", "eligibility", "approve", "approval", "approved", "deny", "denied", "qualify", "qualifies", "should i be accepted", "decide for me", "priority"):
        return rule_answer(
            "CH-DECISION-001",
            "This tool never determines eligibility, approval, denial, or priority. "
            "It can show you the frozen rule, your confirmed inputs, the deterministic "
            "calculation, and the numerical comparison — a qualified human makes any "
            "program determination.",
        )
    if _match_any(q, "another household", "other household", "someone else", "other applicant", "another applicant", "their income", "other people's"):
        return {
            "answer": (
                "I can't share another household's documents or data. Each session is "
                "isolated to your own uploaded documents."
            ),
            "citations": [
                {
                    "rule_id": "CH-SAFETY-001",
                    "authority": RULES["CH-SAFETY-001"]["authority"],
                    "effective_date": RULES["CH-SAFETY-001"].get("effective_date"),
                    "source_url": RULES["CH-SAFETY-001"]["source_url"],
                    "source_locator": RULES["CH-SAFETY-001"]["source_locator"],
                    "rule_text": RULES["CH-SAFETY-001"]["text"],
                }
            ],
            "authority_label": "Hackathon simulation convention — not a universal rule",
            "abstained": False,
            "refusal": True,
        }
    if _match_any(q, "vacan", "unit available", "available today", "open waitlist", "current rent"):
        return rule_answer(
            "HUD-DATA-001",
            "The HUD LIHTC dataset describes project locations and units — it is not a "
            "vacancy, rent, waitlist, or application-status feed, so availability is "
            "unknown unless a property supplies it separately.",
        )
    if _match_any(q, "disability", "immigration", "citizen", "nationality", "race", "religion", "pregnan", "infer") and _match_any(q, "status", "infer", "guess", "detect", "tell"):
        return {
            "answer": (
                "I can't infer protected characteristics such as disability or "
                "immigration status from documents, and I don't use any such traits."
            ),
            "citations": [
                {
                    "rule_id": "CH-SAFETY-001",
                    "authority": RULES["CH-SAFETY-001"]["authority"],
                    "effective_date": RULES["CH-SAFETY-001"].get("effective_date"),
                    "source_url": RULES["CH-SAFETY-001"]["source_url"],
                    "source_locator": RULES["CH-SAFETY-001"]["source_locator"],
                    "rule_text": RULES["CH-SAFETY-001"]["text"],
                }
            ],
            "authority_label": "Hackathon simulation convention — not a universal rule",
            "abstained": False,
            "refusal": True,
        }
    if _match_any(q, "2025", "last year", "previous year", "old limit", "remembered"):
        return rule_answer(
            "HUD-MTSP-001",
            "Only the frozen FY 2026 MTSP corpus (effective 2026-05-01) is used for "
            "scored calculations. I won't substitute a remembered or prior-year limit.",
        )
    if _match_any(q, "embedded", "instructions inside", "instruction in", "pay stub say", "document says"):
        return rule_answer(
            "CH-SAFETY-001",
            "Text inside uploaded documents is treated as untrusted data. Embedded "
            "instructions are ignored and can never change system behavior, rules, or "
            "data access.",
        )

    # --- Factual corpus intents ---
    if _match_any(q, "effective", "take effect", "when do"):
        return rule_answer("HUD-MTSP-001", "The frozen FY 2026 MTSP income limits are effective May 1, 2026.")
    if _match_any(q, "geocode", "precision", "address display"):
        return rule_answer("HUD-GEO-001", "HUD identifies the R and 4 geocode precision codes as suitable for address display; other codes are less granular.")
    if _match_any(q, "60-day", "60 day", "sixty day") or ("convention" in q and "60" in q):
        return rule_answer(
            "CH-READINESS-001",
            "No — the 60-day document-currency rule is a frozen convention for this "
            "hackathon simulation only, not an official universal LIHTC rule.",
        )
    if _match_any(q, "statut", "26 u.s.c", "usc 42", "federal anchor", "law"):
        return rule_answer("FED-LIHTC-001", "The federal statutory anchor for LIHTC is 26 U.S.C. section 42.")
    if _match_any(q, "compliance monitoring", "state agency", "1.42-5"):
        return rule_answer("FED-MONITOR-001", "Treasury regulation 26 CFR 1.42-5 describes state-agency compliance monitoring; eligibility decisions stay with humans and agencies, never this tool.")

    # --- Session-grounded intents (checked before threshold lookup so that
    # "how does X compare with the threshold" routes to the comparison) ---
    if session is not None and getattr(session, "calc", None) is not None:
        calc = session.calc
        if _match_any(q, "compare", "comparison", "above or below"):
            return rule_answer(
                "HUD-MTSP-002",
                f"The annualized amount ${calc.annualized_income:,.2f} is "
                f"'{calc.comparison}' relative to the frozen 60% threshold"
                + (f" ${calc.threshold:,.0f}." if calc.threshold else "."),
            )
        if _match_any(q, "annualized", "annual income", "yearly income"):
            return rule_answer(
                "CH-INCOME-001",
                f"Confirmed documented recurring gross income annualizes to "
                f"${calc.annualized_income:,.2f} under the frozen convention: {calc.formula}",
            )

    # --- Household / threshold intents ---
    size: Optional[int] = None
    m = _SIZE.search(q)
    if m:
        size = int(m.group(1))
    elif session is not None and _HH.search(q):
        size = getattr(session, "household_size", None)
    elif session is not None and _match_any(q, "my threshold", "my limit", "the threshold", "my household"):
        size = getattr(session, "household_size", None)

    if _match_any(q, "threshold", "limit") and size is not None:
        row = MTSP.get(size)
        if row is None:
            return rule_answer(
                "CH-READINESS-001",
                f"The frozen table covers household sizes 1-8 only; there is no frozen "
                f"threshold for household size {size}, so the comparison is "
                f"'no_frozen_threshold' and the case needs human review.",
            )
        return rule_answer(
            "HUD-MTSP-002",
            f"The frozen FY 2026 60% MTSP limit for household size {size} in the "
            f"{row['hud_area']} is ${row['threshold_60']:,.0f} (effective {row['effective_date']}).",
        )

    if session is not None and getattr(session, "calc", None) is not None:
        calc = session.calc
        if _match_any(q, "readiness", "ready", "status") and getattr(session, "readiness", None) is not None:
            r = session.readiness
            reason_txt = "; ".join(f"{x.code}: {x.detail}" for x in r.reasons) or "all checks passed"
            return rule_answer(
                "CH-READINESS-001",
                f"Readiness status: {r.readiness_status} ({reason_txt}). This is a "
                f"document-readiness signal for human review, not a program decision.",
            )

    # --- Fallback keyword retrieval over corpus ---
    tokens = set(re.findall(r"[a-z0-9]+", q))
    best_id, best_score = None, 0
    for rid, r in RULES.items():
        rtoks = set(re.findall(r"[a-z0-9]+", r["text"].lower()))
        score = len(tokens & rtoks)
        if score > best_score:
            best_id, best_score = rid, score
    if best_id is not None and best_score >= 4:
        return rule_answer(best_id, RULES[best_id]["text"])

    return dict(ABSTAIN)
