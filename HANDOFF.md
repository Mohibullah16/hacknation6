# RealDoor — Session Handoff / Build State

_Last updated: 2026-07-19 (after Phase 4, API layer). If a new Claude session picks this up: read this file, `C:\Users\mohib\.claude\plans\ok-so-the-doc-idempotent-crescent.md` (full plan), and run the two eval commands below before changing anything._

## Where things stand

| Phase | Status |
|---|---|
| 1. Scaffold, pack data, deps | ✅ done |
| 2. Extraction engine (text-layer + OCR) | ✅ done — 159/159 gold fields |
| 3. Calc + readiness + citations + submissions | ✅ done — all gold checklists reproduced |
| 4. FastAPI + session/privacy/safety + smoke test | ✅ done — `eval/api_smoke.py` all-pass |
| 5. Frontend (React+Vite, WCAG 2.2 AA) | ⬜ TODO |
| 6. Packet/Discover UI polish | ⬜ TODO (backend endpoints exist) |
| 7. Docs + demo script + video + final eval | ⬜ TODO |

## Verify current state (run from `realdoor/`)

```
python eval/run_eval.py    # must print WEIGHTED TOTAL 100.00%
python eval/api_smoke.py   # must print "API smoke: ALL PASS"
```

Deps (already installed via `pip install --user`): fastapi uvicorn[standard] pdfplumber pypdfium2 rapidocr-onnxruntime python-multipart jsonschema httpx. Python 3.12.10, Node 24.11.

Run the API: `cd backend; python -m uvicorn app.main:app --reload --port 8000`

## Architecture map (backend)

- `backend/app/config.py` — frozen constants, field allowlist, paths, 60-day convention.
- `backend/app/extraction/` — `textlayer.py` (pdfplumber, watermark chars filtered by size≥20), `ocr.py` (pypdfium2 render ×3 + RapidOCR, pixel→point mapping, watermark boxes dropped by height>24pt), `labeling.py` (label-anchor extraction, concatenation-tolerant because OCR merges words like 'PAYPERIOD'; bbox padded to min 24×14pt to match gold), `parse.py` (typed normalizers; camel/digit re-spacing for OCR'd names/addresses), `pipeline.py` (routing, allowlist, abstention <0.6 confidence, injection detection).
- `backend/app/calc/engine.py` — income model: **latest pay stub only** (stubs are consecutive periods, never summed; falls back to older stub if newest unusable), components (hours×rate) authoritative over displayed gross (conflict → flag), benefit monthly×12, gig gross_receipts×12 uncorroborated flag, application_summary NEVER income (unsigned claim). Reuses `starter_calculate.py` verbatim.
- `backend/app/readiness/engine.py` — reason codes drive NEEDS_REVIEW: PAY_STUB_TOTAL_CONFLICT, {TYPE}_EXPIRED (60d before 2026-07-18), GIG_INCOME_UNCORROBORATED, HOUSEHOLD_SIZE_OUT_OF_TABLE, MISSING_CITATION, NO_INCOME_EVIDENCE, UNCONFIRMED_EVIDENCE. **Missing docs are informational gaps, never status gates** (gold: HH-003/006 READY despite missing employment letter).
- `backend/app/rules/corpus.py` — 11-rule frozen corpus, MTSP lookup, intent-routed Q&A (36/36 gold). Order matters: safety intents → compare/annualized (session) → threshold → factual → keyword fallback → abstain.
- `backend/app/safety/guards.py` — injection patterns, decision-language gate (`enforce_no_decision_language` — for LLM text only; templates are pre-vetted and deliberately mention 'approval' in negated context, don't gate them), `validate_bbox`.
- `backend/app/privacy/store.py` — in-memory sessions, TTL 4h, audit log (never raw values), hard delete. `packet.py` — preview JSON + printable HTML + export ZIP.
- `backend/app/main.py` — endpoints: POST /api/session (consent gate) · POST .../documents (upload→extract) · PATCH .../fields/{f} (confirm|correct → recompute) · POST .../confirm-all · GET .../calculation (blocked until all fields confirmed) · POST .../qa · GET .../packet + /packet/export (ZIP) · GET .../audit · DELETE session · GET /api/rules · GET /api/properties (Discover: availability always "unknown", 32 rows unfiltered).

## What remains (in order)

1. **Frontend** (`frontend/`, not yet created): `npm create vite@latest frontend -- --template react-ts`. Pages: Consent/landing → Profile (upload, field table w/ confidence chips + confirm/correct, pdf.js evidence viewer with bbox overlays — convert bottom-left-origin points to top-left CSS: `top = (792 - y2) * scale`) → Understand (calc card: value/threshold/formula/rule/effective date + Q&A panel) → Prepare (gaps, packet preview, export ZIP button, delete-session button) → Discover (table of 32 properties, availability column always "Unknown", renter-chosen filters only, always show unfiltered count). 
   A11y (15% of judge rubric!): skip link, semantic landmarks, single h1 per page, visible focus ring, aria-live="polite" status region for extract/recompute/export/delete announcements, labels + aria-describedby errors, icon+text status (no color-only), keyboard-complete, contrast ≥4.5:1, target ≥24px.
2. **Docs** (`docs/`): architecture-risk-note.md (required deliverable), feature-manifest.md (every feature + purpose — "no hidden proxies" requirement), a11y.md (WCAG checklist + how verified), demo-script.md (map 1:1 to the 6 Required Acceptance Demo steps in the challenge PDF).
3. **README.md** — setup, run, eval, screenshot.
4. **Demo video** — follow demo-script.md.
5. Final `git commit`; re-run both evals last.

## Scoring context (why decisions look like they do)

- Judge rubric: Profile 25 / Rules&math 25 / Safety 20 / **Accessibility 15** / End-to-end 15. Auto-lose: any approve/deny/score/rank/suppress output.
- Pack eval: extraction 35 / calc 25 / readiness 20 / citations 10 / adversarial 10; hidden tests perturb values but keep schemas → nothing hardcoded.
- The 6-step Required Acceptance Demo (challenge PDF p.2) is fully covered by `eval/api_smoke.py` at API level; the frontend must make each step clickable.
