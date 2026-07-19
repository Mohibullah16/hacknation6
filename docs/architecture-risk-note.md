# RealDoor — Architecture & Risk Note

_Hack-Nation 6th Global AI Hackathon · Challenge 03 (RealPage) · Team submission document_

## What this is

A renter-side **application-readiness copilot** for one frozen scenario: Boston-Cambridge-Quincy MA-NH HMFA, LIHTC-style flow, FY 2026 MTSP limits (effective 2026-05-01), event date frozen to 2026-07-18. It extracts allowlisted evidence from synthetic documents, requires renter confirmation, explains frozen rules with citations, runs deterministic income math, flags document gaps, and exports a renter-controlled packet. **It never determines eligibility, approval, denial, priority, or availability.**

## Architecture

```
React + Vite frontend (WCAG 2.2 AA)          FastAPI backend (Python 3.12)
┌─────────────────────────────┐   /api   ┌──────────────────────────────────┐
│ Consent → Profile →         │ ───────► │ extraction/  pdfplumber + RapidOCR│
│ Understand → Prepare        │          │ calc/        deterministic math   │
│ (+ Discover, stretch)       │ ◄─────── │ readiness/   reason-code engine   │
│ pdf.js evidence overlays    │          │ rules/       frozen corpus + Q&A  │
└─────────────────────────────┘          │ safety/      firewall + gates     │
                                         │ privacy/     in-memory sessions   │
                                         └──────────────────────────────────┘
```

**Extraction.** Text-layer PDFs: pdfplumber word extraction with watermark glyphs filtered by font size, then label-anchor field capture (label row above value row). Rasterized PDFs: pypdfium2 render → RapidOCR (local ONNX models, no cloud) → pixel-to-PDF-point mapping so citations use the same coordinate system. Only the 21 allowlisted fields can ever be extracted; everything else in a document is ignored. Confidence below 0.60 → the field **abstains** (value withheld, renter must type it).

**Determinism.** All scored math is plain arithmetic: annualize(amount, frequency) with fixed multipliers, threshold lookup from the frozen MTSP table, string-free comparison. The organizer starter functions are used verbatim. No LLM output ever becomes a number, a threshold, or a status.

**Model disclosure (per pack release-gate rule; see also `docs/model-license-manifest.md`).** Every scored path — extraction, calculation, readiness, citations — is local and deterministic (RapidOCR runs local ONNX weights, Apache-2.0). An **optional OpenAI assist** activates only when an `OPENAI_API_KEY` is present and is disclosed on the consent screen. Its entire permitted surface is: (1) *routing* a free-text rules question to one of the vetted answer templates (the model picks an intent name from a fixed enum, validated server-side — it never authors answer text); (2) adding a *plain-language rephrasing* beside the authoritative cited answer, discarded unless it passes both the decision-language deny gate and a number-grounding check (no number may appear that is not already in the deterministic answer); and (3) an opt-in, off-by-default advisory extraction cross-check whose notes never change a value or a status. No LLM output ever becomes a number, a threshold, or a status. With no key, the app runs fully offline with identical scored behavior.

**Human decision boundary.** The API cannot express an eligibility decision: the submission schema has no such field, and refusal templates deflect "decide for me" requests to rule + confirmed input + calculation. Two classes of text are guarded differently, deliberately: vetted templates are safe **by construction** and shown verbatim (they legitimately quote "approval/denial" in negated context, so running the deny-list over them would break correct refusals); all **LLM-generated** text passes the decision-language deny-list plus number-grounding before display and falls back to the deterministic template on failure. Refusal and safety templates are never rephrased at all.

## Data flow & privacy

- Consent screen enumerates every data use before upload; consent is logged.
- Uploads live **only in process memory**, keyed by session UUID, TTL 4 h; nothing is written to disk (uploads touch a per-request temp dir only during parsing and are deleted immediately).
- Audit log records events, field names, document ids, and rule-corpus version — never values or contents.
- Export is an explicit renter-initiated local ZIP download; there is no send-to-property capability anywhere in the codebase.
- Delete-session erases documents, bytes, results, and logs immediately; the UI confirms and announces it.
- No training on uploads; no analytics. The only third-party call is the optional, consent-screen-disclosed OpenAI Q&A assist (typed questions only; documents are never sent unless the separate cross-check flag is explicitly opted into, and then only allowlisted synthetic field values). With no API key there are no third-party calls at all.
- Prompt-injection resistance extends to the LLM path: question text and rule text are declared untrusted data in every prompt, the router's output is validated against a fixed intent enum, and rephrasings are gated + grounded — a hostile question can at worst select a different vetted template.

## Threat model & mitigations

| Risk | Mitigation | Verified by |
|---|---|---|
| Prompt injection inside documents | Document text is data, never instructions; instruction-like lines detected, stripped, and surfaced to the renter ("detected and ignored" banner) | ADV-001/013, api_smoke |
| Eligibility overreach ("am I approved?") | Refusal templates + decision-language output gate + schema with no decision field | ADV-003/015 |
| Cross-applicant leakage | Sessions isolated by UUID; no cross-session endpoint exists; Q&A refuses | ADV-002/014 |
| Vacancy hallucination | Discover labels availability "unknown" on every row; Q&A cites HUD-DATA-001 | ADV-004/016 |
| Wrong-year limits | Only the frozen FY 2026 corpus is loadable; requests for 2025 limits are refused with citation | ADV-005/017 |
| Uncited values | Traceability gate: uncited income ⇒ MISSING_CITATION ⇒ NEEDS_REVIEW; bbox validation rejects out-of-page boxes | ADV-006/018, ADV-010/022 |
| Protected-trait inference | No such features exist (see feature manifest); Q&A refuses inference requests | ADV-009/021 |
| Extraction error harming the renter | Extraction-path confidence signal (digital text 0.97 · OCR ≤0.85 scaled by OCR score · halved on parse failure), hard abstention below 0.60, mandatory renter confirm/correct before any downstream use; correction recomputes everything | acceptance demo step 2; `demo/demo_pay_stub_lowquality.pdf` abstention beat |
| LLM assist overreach (hallucinated numbers or decisions) | Router constrained to a validated intent enum; rephrasings pass decision-language deny-list + number-grounding or are discarded; refusal/safety templates never rephrased; cross-check advisory-only and off by default | with-key manual tests in demo-script step 3 |
| Stale/conflicting evidence slipping through | 60-day currency convention (labeled as simulation-only), component-vs-total reconciliation, gig corroboration check | ADV-007/008/012 |

## Known limitations

- One metro, one program, one rule year — by design (frozen scenario).
- Layout-anchored extraction targets the pack's document schema; unseen layouts abstain rather than guess (values fall back to renter entry).
- The 60-day currency rule and readiness reason codes are hackathon conventions, clearly labeled as such in the UI and packet.
- In-memory sessions do not survive a server restart — acceptable for a research prototype; a production build would need encrypted storage with the same delete semantics.

## Verification

`python eval/run_eval.py` → 100.0% on **our local reproduction of the pack's checks**: extraction (159/159 gold fields incl. all rasterized docs), calculation (18/18), readiness (18/18), citations (24/24), a 24-test adversarial suite exercising each pack category, and the 36 gold Q&A. `python eval/api_smoke.py` walks all six Required Acceptance Demo steps against the live API. Both run fully offline (no `OPENAI_API_KEY`), which also proves the assist layer is strictly additive.

To be precise about scope: this harness is our own reproduction, not the judges' scoring. The official judging rubric is Profile accuracy 25% · Rules & math 25% · Safety & privacy 20% · Accessibility 15% · End-to-end usefulness 15% — the accessibility and end-to-end criteria are judged live in the demo (see `docs/a11y.md` and `docs/demo-script.md`), not by this harness. See `docs/demo-script.md`.
