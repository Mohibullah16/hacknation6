# RealDoor — Application-Readiness Copilot

Renter-side copilot for the Hack-Nation 6th Global AI Hackathon, **Challenge 03 (RealPage)**.
It turns synthetic household documents into a **renter-confirmed** profile, explains one frozen
affordable-housing rule set **with citations**, runs **deterministic** income math, flags missing or
expired documents, and builds a **renter-controlled** packet — and it **never** decides eligibility,
approval, denial, priority, or availability.

> The AI extracts, explains, retrieves, calculates, and prepares. The renter confirms. A qualified human decides.

## Quick start

Requirements: Python 3.12+, Node 18+.

```powershell
# 1. Backend deps (pip-only, no system binaries; OCR runs locally via ONNX)
pip install fastapi "uvicorn[standard]" pdfplumber pypdfium2 rapidocr-onnxruntime python-multipart jsonschema httpx

# 2. Run the API
cd backend
python -m uvicorn app.main:app --port 8000

# 3. Run the frontend (separate terminal)
cd frontend
npm install
npm run dev          # open http://localhost:5173
```

Synthetic test documents live in `backend/pack_data/synthetic_documents/documents/`.

## Reproduce the scores

```powershell
python eval/run_eval.py    # pack-weighted scorecard → 100.00%
python eval/api_smoke.py   # all 6 Required Acceptance Demo steps at API level → ALL PASS
```

`run_eval.py` mirrors the organizer evaluation mix (extraction 35 · calc 25 · readiness 20 ·
citations 10 · safety/adversarial 10) against the pack's gold data: 159/159 fields (including the 8
scanned documents via local OCR), 6/6 households, 36/36 gold Q&A, 24/24 adversarial tests. Nothing is
hardcoded — swap in perturbed fixtures with the same schemas and the pipeline re-extracts genuinely.

## The three-stage journey

1. **Profile** — upload PDFs; only 21 allowlisted fields are extracted, each with page + source box +
   calibrated confidence; low confidence abstains; nothing feeds the math until you confirm or correct it.
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
| [docs/feature-manifest.md](docs/feature-manifest.md) | Every feature and its purpose (no hidden proxies) |
| [docs/a11y.md](docs/a11y.md) | WCAG 2.2 AA implementation and verification protocol |
| [docs/demo-script.md](docs/demo-script.md) | 6-step acceptance demo, rehearsal checklist |
| [HANDOFF.md](HANDOFF.md) | Build-state map for contributors |

## Safety posture (demonstrated, not disclaimed)

- Document text is untrusted: embedded instructions are detected, ignored, and surfaced to the renter.
- Decision language is structurally impossible: no schema field, refusal templates, output deny-list gate.
- Sessions are memory-only, audit logs contain no document contents, export is local-download only,
  deletion is immediate and total. No training on uploads. No third-party calls at runtime.

Built on the organizer starter pack (frozen FY 2026 MTSP limits effective 2026-05-01; synthetic
documents only). Research prototype — not legal advice, not a housing decision system.
