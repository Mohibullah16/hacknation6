# RealDoor — Session Handoff / Build State

_Last updated: 2026-07-19 (correction + OpenAI-assist build **COMPLETE and verified**). If a new Claude session picks this up: read this file, then `C:\Users\mohib\.claude\plans\build-plan-for-all-pure-summit.md` (the executed plan, full rationale). Run the verify commands below before changing anything._

## Where things stand — everything code-side is DONE

| Work | Status |
|---|---|
| Original build (extraction/calc/readiness/rules/safety/privacy/frontend/docs) | ✅ |
| Rubric-review corrections (A1 gate wiring truthful, A2 abstention demonstrable + honest confidence wording, A3 "100%" reframed as local reproduction, A4 paraphrase intents, A5 dialog focus + .done stepper + dead-code) | ✅ |
| OpenAI assist (route → vetted intents · gated+grounded plain_language · opt-in advisory crosscheck) | ✅ code complete |
| Disclosure: `GET /api/config`, consent-screen banner, Understand badges, `docs/model-license-manifest.md` (required deliverable) | ✅ |
| Degraded demo doc `demo/demo_pay_stub_lowquality.pdf` (hourly_rate abstains at 0.485; regenerate/verify via `python scripts/make_demo_doc.py`) | ✅ |
| `backend/requirements.txt` (incl. `openai`, installed: 1.109.1) | ✅ |
| **Verified offline:** `run_eval.py` 100.00% all sections · `api_smoke.py` ALL PASS · `/api/config` all-false with no key · QA carries `assist_used=False` · `npm run build` clean (pre-existing pdfjs chunk-size warning only) | ✅ |

## What remains (user tasks)

1. ~~With-key verification~~ ✅ **DONE** — user's key is in `backend/.env` (gitignored; loaded via python-dotenv; template at `.env.example`) with `OPENAI_MODEL=gpt-5.4-nano`; `python scripts/test_llm_assist.py` → **LLM assist: ALL PASS** (paraphrase routing to correct rules, grounded plain_language, hostile prompts deflected).
2. **Rehearse + record the demo video** per `docs/demo-script.md` — now includes the abstention beat (step 1) and the AI beat (step 3, key required).
3. `git add -A; git commit` and publish the repo (`.env` is ignored; double-check with `git status`).

## LLM API gotchas (learned with-key)

- gpt-5.x family rejects `max_tokens` (use `max_completion_tokens`) and non-default temperature — `_chat_json` in `llm/assist.py` uses `max_completion_tokens=2000`, no temperature (reasoning models spend completion budget on reasoning; outputs are gated anyway, determinism not needed).
- Both eval harnesses force `REALDOOR_LLM_ASSIST=0` before importing the app, so they always measure the deterministic engine even with a key in `.env` (re-verified: run_eval 100.00%, api_smoke ALL PASS with key present).

## Verify current state (run from `realdoor/`)

```
python eval/run_eval.py       # WEIGHTED TOTAL 100.00%
python eval/api_smoke.py      # API smoke: ALL PASS
python scripts/make_demo_doc.py   # OK: hourly_rate abstains...
cd frontend; npm run build    # ✓ built
```

All four pass as of this handoff (no `OPENAI_API_KEY` set — that's the offline-identical guarantee).

## Architecture map (backend)

- `config.py` — frozen constants + field allowlist + LLM env flags at bottom (`LLM_ASSIST/EXPLAIN` on-with-key; `LLM_CROSSCHECK` opt-in via `REALDOOR_LLM_CROSSCHECK=1`).
- `extraction/` — textlayer (pdfplumber, watermark chars ≥20pt filtered) · ocr (pypdfium2×3 + RapidOCR) · labeling (label-anchor, concat-tolerant, bbox min 24×14) · parse (typed normalizers) · pipeline (allowlist, abstain <0.60, injection detect).
- `calc/engine.py` — latest-stub-only wages, components beat displayed gross, benefits ×freq, gig ×12, application summary never income.
- `readiness/engine.py` — reason codes drive NEEDS_REVIEW; missing docs = informational gaps only.
- `rules/corpus.py` — **intent registry**: `_intent_*` builders, `INTENT_BUILDERS`, `INTENT_DESCRIPTIONS` (the LLM router's enum incl. "abstain"), `build_intent_answer`. Keyword router `answer_question` dispatches into the same builders. **Answer strings are load-bearing** — gold Q&A string-matches them; never reword.
- `llm/assist.py` — OpenAI (user's explicit choice over Claude). `route_question` (JSON mode, enum-validated), `plain_language` (deny-gate + `_grounded` number check, None on failure), `crosscheck_fields` (advisory, gated). Lazy client, 12s timeout, temperature 0; graceful degrade if package/key missing.
- `safety/guards.py` — injection patterns; `enforce_no_decision_language` applies to LLM text only (templates vetted by construction — docstring explains why).
- `privacy/` — in-memory store TTL 4h, audit (no values), packet ZIP.
- `main.py` — endpoints as before + `GET /api/config`. `rules_qa`: keyword router → (if abstained + enabled) LLM route → vetted builder → optional `plain_language` (never for refusals or CH-DECISION/CH-SAFETY citations). Upload attaches `advisory_flags` only when crosscheck opted in.

## Frontend map

`api.ts` (types + `getConfig`) · `Landing.tsx` (AI disclosure banner pre-consent) · `Profile.tsx` (advisory chips; abstained chip = the demo doc beat) · `Understand.tsx` (assist chip + plain-language panel; suggested Q includes the paraphrase "Do I earn too much for this program?" which also routes offline via keywords) · `Prepare.tsx` (alertdialog focus in/Escape/return) · `App.tsx` (.done stepper for visited steps 1-3).

## Gotchas for future changes

- `api_smoke.py` globs `hh-005_*.pdf` and asserts exactly 4 docs → demo assets stay in `demo/`, never pack documents dir.
- Demo doc: pay_date 2026-06-13 is deliberate (older than D02 2026-06-27 → excluded by latest-stub rule; newer than cutoff 2026-05-19 → no EXPIRED flag); values consistent 68×26=1768 so no conflict after correction.
- Never claim "100%" as a challenge score — it's our local reproduction (docs already worded this way; keep it).
- Judge rubric: Profile 25 / Rules&math 25 / Safety 20 / Accessibility 15 / E2E 15. Auto-lose: approve/deny/score/rank/suppress.
