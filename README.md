# RealDoor — Application-Readiness Copilot

Renter-side copilot for the Hack-Nation 6th Global AI Hackathon, **Challenge 03 (RealPage)**.
It turns synthetic household documents into a **renter-confirmed** profile, explains one frozen
affordable-housing rule set **with citations**, runs **deterministic** income math, flags missing or
expired documents, and builds a **renter-controlled** packet — and it **never** decides eligibility,
approval, denial, priority, or availability.

**Deterministic by design, with a disclosed AI explainer.** Every scored number, threshold,
comparison, and readiness status comes from a local deterministic engine. An optional OpenAI assist
(active only when `OPENAI_API_KEY` is set, disclosed on the consent screen) routes free-text
questions to vetted cited answers and adds gated plain-language rephrasings — it can never introduce
a number or a decision. See [docs/model-license-manifest.md](docs/model-license-manifest.md).

> The AI extracts, explains, retrieves, calculates, and prepares. The renter confirms. A qualified human decides.

## Quick start

Requirements: Python 3.12+, Node 18+.

```powershell
# 1. Backend deps (pip-only, no system binaries; OCR runs locally via ONNX)
pip install -r backend/requirements.txt

# 2. Run the API
cd backend
# optional AI assist: put your key in backend/.env (copy .env.example; gitignored) — leave empty for fully-local mode
python -m uvicorn app.main:app --port 8000

# 3. Run the frontend (separate terminal)
cd frontend
npm install
npm run dev          # open http://localhost:5173
```

Synthetic test documents live in `backend/pack_data/synthetic_documents/documents/`.

## Reproduce the scores

```powershell
python eval/run_eval.py    # our local reproduction of the pack checks → 100.00%
python eval/api_smoke.py   # all 6 Required Acceptance Demo steps at API level → ALL PASS
```

`run_eval.py` is **our local reproduction** of the organizer evaluation mix (extraction 35 · calc 25 ·
readiness 20 · citations 10 · safety/adversarial 10) against the pack's gold data: 159/159 fields
(including the 8 scanned documents via local OCR), 6/6 households, 36/36 gold Q&A, and one assertion
per pack adversarial category. Nothing is hardcoded — swap in perturbed fixtures with the same schemas
and the pipeline re-extracts genuinely. Both commands run fully offline (no API key), which also
proves the AI assist is strictly additive.

The official judging rubric weighs Profile accuracy 25 · Rules & math 25 · Safety & privacy 20 ·
**Accessibility 15 · End-to-end usefulness 15**; the last two are judged live in the demo
([docs/a11y.md](docs/a11y.md), [docs/demo-script.md](docs/demo-script.md)), not by this harness.

## The three-stage journey

1. **Profile** — upload PDFs; only 21 allowlisted fields are extracted, each with page + source box +
   an extraction-path confidence signal; below 60% the tool **abstains** and the renter types the value
   (try `demo/demo_pay_stub_lowquality.pdf`); nothing feeds the math until you confirm or correct it.
2. **Understand** — deterministic annualization with visible formulas, the frozen 60% MTSP threshold with
   rule id / effective date / official source link, and a rules Q&A that answers **only** from the frozen
   corpus with citations (and abstains otherwise).
3. **Prepare** — reason-coded readiness (READY_TO_REVIEW / NEEDS_REVIEW), checklist gaps with guidance,
   packet preview, local ZIP export, audit log, and one-click full deletion.
4. **Discover** *(stretch)* — the 32 public HUD LIHTC records, availability always "unknown",
   renter-selected filters only, unfiltered count always shown.

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture-risk-note.md](docs/architecture-risk-note.md) | Architecture, data flow, threat model, model disclosure, limitations |
| [docs/feature-manifest.md](docs/feature-manifest.md) | Every feature and its purpose (no hidden proxies), incl. exactly what the optional AI assist may see |
| [docs/model-license-manifest.md](docs/model-license-manifest.md) | Data, model, and code license manifest (required deliverable) |
| [docs/a11y.md](docs/a11y.md) | WCAG 2.2 AA implementation and verification protocol |
| [docs/demo-script.md](docs/demo-script.md) | 6-step acceptance demo, rehearsal checklist |
| [HANDOFF.md](HANDOFF.md) | Build-state map for contributors |

## Safety posture (demonstrated, not disclaimed)

- Document text is untrusted: embedded instructions are detected, ignored, and surfaced to the renter.
- Decision language is structurally impossible: no schema field, refusal templates, output deny-list gate.
- Sessions are memory-only, audit logs contain no document contents, export is local-download only,
  deletion is immediate and total. No training on uploads. With no API key there are no third-party
  calls at all; with one, the only third-party call is the consent-screen-disclosed OpenAI Q&A assist
  (typed questions — never documents), whose output is deny-gated and number-grounded before display.

Built on the organizer starter pack (frozen FY 2026 MTSP limits effective 2026-05-01; synthetic
documents only). Research prototype — not legal advice, not a housing decision system.
