"""Frozen rule corpus loader, MTSP threshold lookup, and citation-gated Q&A.

The Q&A engine is deterministic retrieval over the 11 frozen rules plus a
registry of named intent builders for the scored question shapes. Two routers
dispatch into the same registry:

  1. the keyword router in `answer_question` (always available, offline), and
  2. the optional LLM router (`app.llm.assist.route_question`), which may only
     *classify* a free-text question into one of these named intents — the
     answer text and citation always come from the vetted builders below.

The engine abstains when nothing in the frozen corpus answers the question and
never emits eligibility language: every answer string in this module is a
pre-vetted template.
"""
from __future__ import annotations

import csv
import json
import re
from typing import Callable, Optional

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


def _refusal_answer(rule_id: str, answer: str) -> dict:
    d = rule_answer(rule_id, answer)
    d["refusal"] = True
    return d


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


# ---------------------------------------------------------------------------
# Intent builders — every answer string is a vetted template. Builders take the
# session (may be None) and return an answer dict, or None when the intent
# needs session context that is missing (the caller then abstains).
# ---------------------------------------------------------------------------

def _intent_decision_refusal(session=None) -> dict:
    return rule_answer(
        "CH-DECISION-001",
        "This tool never determines eligibility, approval, denial, or priority. "
        "It can show you the frozen rule, your confirmed inputs, the deterministic "
        "calculation, and the numerical comparison — a qualified human makes any "
        "program determination.",
    )


def _intent_cross_household_refusal(session=None) -> dict:
    return _refusal_answer(
        "CH-SAFETY-001",
        "I can't share another household's documents or data. Each session is "
        "isolated to your own uploaded documents.",
    )


def _intent_trait_refusal(session=None) -> dict:
    return _refusal_answer(
        "CH-SAFETY-001",
        "I can't infer protected characteristics such as disability or "
        "immigration status from documents, and I don't use any such traits.",
    )


def _intent_vacancy_limitation(session=None) -> dict:
    return rule_answer(
        "HUD-DATA-001",
        "The HUD LIHTC dataset describes project locations and units — it is not a "
        "vacancy, rent, waitlist, or application-status feed, so availability is "
        "unknown unless a property supplies it separately.",
    )


def _intent_frozen_year(session=None) -> dict:
    return rule_answer(
        "HUD-MTSP-001",
        "Only the frozen FY 2026 MTSP corpus (effective 2026-05-01) is used for "
        "scored calculations. I won't substitute a remembered or prior-year limit.",
    )


def _intent_embedded_instructions(session=None) -> dict:
    return rule_answer(
        "CH-SAFETY-001",
        "Text inside uploaded documents is treated as untrusted data. Embedded "
        "instructions are ignored and can never change system behavior, rules, or "
        "data access.",
    )


def _intent_effective_date(session=None) -> dict:
    return rule_answer("HUD-MTSP-001", "The frozen FY 2026 MTSP income limits are effective May 1, 2026.")


def _intent_geocode_precision(session=None) -> dict:
    return rule_answer("HUD-GEO-001", "HUD identifies the R and 4 geocode precision codes as suitable for address display; other codes are less granular.")


def _intent_currency_convention(session=None) -> dict:
    return rule_answer(
        "CH-READINESS-001",
        "No — the 60-day document-currency rule is a frozen convention for this "
        "hackathon simulation only, not an official universal LIHTC rule.",
    )


def _intent_statute(session=None) -> dict:
    return rule_answer("FED-LIHTC-001", "The federal statutory anchor for LIHTC is 26 U.S.C. section 42.")


def _intent_compliance_monitoring(session=None) -> dict:
    return rule_answer("FED-MONITOR-001", "Treasury regulation 26 CFR 1.42-5 describes state-agency compliance monitoring; eligibility decisions stay with humans and agencies, never this tool.")


def _intent_comparison(session=None) -> Optional[dict]:
    calc = getattr(session, "calc", None) if session is not None else None
    if calc is None:
        return None
    return rule_answer(
        "HUD-MTSP-002",
        f"The annualized amount ${calc.annualized_income:,.2f} is "
        f"'{calc.comparison}' relative to the frozen 60% threshold"
        + (f" ${calc.threshold:,.0f}." if calc.threshold else "."),
    )


def _intent_annualized_income(session=None) -> Optional[dict]:
    calc = getattr(session, "calc", None) if session is not None else None
    if calc is None:
        return None
    return rule_answer(
        "CH-INCOME-001",
        f"Confirmed documented recurring gross income annualizes to "
        f"${calc.annualized_income:,.2f} under the frozen convention: {calc.formula}",
    )


def _intent_threshold(session=None, size: Optional[int] = None) -> Optional[dict]:
    if size is None and session is not None:
        size = getattr(session, "household_size", None)
    if size is None:
        return None
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


def _intent_readiness_status(session=None) -> Optional[dict]:
    if session is None or getattr(session, "readiness", None) is None:
        return None
    r = session.readiness
    reason_txt = "; ".join(f"{x.code}: {x.detail}" for x in r.reasons) or "all checks passed"
    return rule_answer(
        "CH-READINESS-001",
        f"Readiness status: {r.readiness_status} ({reason_txt}). This is a "
        f"document-readiness signal for human review, not a program decision.",
    )


# Every intent the LLM router may select. The router output is validated
# against this set server-side, so a misbehaving model can at worst pick a
# different vetted template — it can never author answer text.
INTENT_BUILDERS: dict[str, Callable[..., Optional[dict]]] = {
    "decision_refusal": _intent_decision_refusal,
    "cross_household_refusal": _intent_cross_household_refusal,
    "trait_refusal": _intent_trait_refusal,
    "vacancy_limitation": _intent_vacancy_limitation,
    "frozen_year": _intent_frozen_year,
    "embedded_instructions": _intent_embedded_instructions,
    "effective_date": _intent_effective_date,
    "geocode_precision": _intent_geocode_precision,
    "currency_convention": _intent_currency_convention,
    "statute": _intent_statute,
    "compliance_monitoring": _intent_compliance_monitoring,
    "comparison": _intent_comparison,
    "annualized_income": _intent_annualized_income,
    "threshold": _intent_threshold,
    "readiness_status": _intent_readiness_status,
}

INTENT_DESCRIPTIONS: dict[str, str] = {
    "decision_refusal": "asks for an eligibility/approval/denial/priority decision or 'decide for me'",
    "cross_household_refusal": "asks about another household's or applicant's documents, income, or data",
    "trait_refusal": "asks to infer protected traits (disability, immigration status, race, religion, ...)",
    "vacancy_limitation": "asks about unit availability, vacancies, open waitlists, or current rents",
    "frozen_year": "asks to use prior-year (e.g. 2025) or remembered income limits",
    "embedded_instructions": "asks about instructions embedded inside uploaded documents",
    "effective_date": "asks when the FY 2026 MTSP income limits take effect",
    "geocode_precision": "asks about geocode precision codes or address display accuracy",
    "currency_convention": "asks whether the 60-day document-currency rule is official or a simulation convention",
    "statute": "asks for the federal statutory anchor / law behind LIHTC",
    "compliance_monitoring": "asks about state-agency compliance monitoring or 26 CFR 1.42-5",
    "comparison": "asks how their income compares with the threshold / are they over or under the limit",
    "annualized_income": "asks what annualized/yearly income the calculation uses",
    "threshold": "asks for the income threshold/limit for their household or a given household size",
    "readiness_status": "asks whether their packet/application is ready or what its readiness status is",
    "abstain": "anything not covered by the frozen corpus intents above",
}


def build_intent_answer(intent: str, session=None) -> Optional[dict]:
    """Dispatch a named intent (e.g. chosen by the LLM router) to its vetted
    builder. Returns None for unknown intents or missing session context."""
    builder = INTENT_BUILDERS.get(intent)
    if builder is None:
        return None
    return builder(session)


def answer_question(question: str, session=None) -> dict:
    """Deterministic keyword router. `session` (optional) provides confirmed
    household context: .household_id, .household_size, .calc (CalcResult),
    .readiness (ReadinessResult)."""
    q = question.lower().strip()

    # --- Safety-sensitive intents first ---
    if _match_any(q, "eligible", "ineligible", "eligibility", "approve", "approval", "approved", "deny", "denied", "qualify", "qualifies", "should i be accepted", "decide for me", "priority"):
        return _intent_decision_refusal(session)
    if _match_any(q, "another household", "other household", "someone else", "other applicant", "another applicant", "their income", "other people's"):
        return _intent_cross_household_refusal(session)
    if _match_any(q, "vacan", "unit available", "available today", "open waitlist", "current rent"):
        return _intent_vacancy_limitation(session)
    if _match_any(q, "disability", "immigration", "citizen", "nationality", "race", "religion", "pregnan", "infer") and _match_any(q, "status", "infer", "guess", "detect", "tell"):
        return _intent_trait_refusal(session)
    if _match_any(q, "2025", "last year", "previous year", "old limit", "remembered"):
        return _intent_frozen_year(session)
    if _match_any(q, "embedded", "instructions inside", "instruction in", "pay stub say", "document says"):
        return _intent_embedded_instructions(session)

    # --- Factual corpus intents ---
    if _match_any(q, "effective", "take effect", "when do"):
        return _intent_effective_date(session)
    if _match_any(q, "geocode", "precision", "address display"):
        return _intent_geocode_precision(session)
    if _match_any(q, "60-day", "60 day", "sixty day") or ("convention" in q and "60" in q):
        return _intent_currency_convention(session)
    if _match_any(q, "statut", "26 u.s.c", "usc 42", "federal anchor", "law"):
        return _intent_statute(session)
    if _match_any(q, "compliance monitoring", "state agency", "1.42-5"):
        return _intent_compliance_monitoring(session)

    # --- Session-grounded intents (checked before threshold lookup so that
    # "how does X compare with the threshold" routes to the comparison) ---
    if session is not None and getattr(session, "calc", None) is not None:
        if _match_any(q, "compare", "comparison", "above or below", "am i over", "am i under", "over the limit", "under the limit", "too much"):
            ans = _intent_comparison(session)
            if ans is not None:
                return ans
        if _match_any(q, "annualized", "annual income", "yearly income", "total income", "income counted"):
            ans = _intent_annualized_income(session)
            if ans is not None:
                return ans

    # --- Household / threshold intents ---
    size: Optional[int] = None
    m = _SIZE.search(q)
    if m:
        size = int(m.group(1))
    elif session is not None and _HH.search(q):
        size = getattr(session, "household_size", None)
    elif session is not None and _match_any(q, "my threshold", "my limit", "the threshold", "my household"):
        size = getattr(session, "household_size", None)

    if _match_any(q, "threshold", "limit", "income limit", "maximum income", "how much can i earn") and size is not None:
        ans = _intent_threshold(session, size)
        if ans is not None:
            return ans

    if session is not None and getattr(session, "calc", None) is not None:
        if _match_any(q, "readiness", "ready", "status") and getattr(session, "readiness", None) is not None:
            ans = _intent_readiness_status(session)
            if ans is not None:
                return ans

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
