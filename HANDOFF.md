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
| Evidence auto-zoom: focusing a field (highlight button or **Correct**) re-renders the PDF at 2× and centers its cited bbox in the scrollable stage (instant, no animation; keyboard-reachable via the existing table buttons; `EvidenceViewer.tsx` + `.pdf-stage.zoomed` CSS). `npm run build` clean; **needs one manual eyeball in the browser before the demo** | ✅ code |
| Judge-style a11y focus-management pass (user hit the bug live): Profile Confirm/Save/Cancel/Confirm-all no longer drop keyboard focus to `<body>` — `pendingFocus` effect moves focus to the next unconfirmed row's **field/zoom button** (user-requested: inspect the source box before confirming; Enter zooms, then Tab → Confirm) / back to Correct / to the `#profile-status` banner (which holds the Step 2 link when done). Understand: focus lands on the answer region after Ask (input on error). Prepare: alertdialog Tab-trapped between its two buttons; post-delete focuses the "Session deleted" heading; 4-s auto-redirect removed (link kept). App: route-change focus skip on initial load. EvidenceViewer: `.pdf-stage` is a focusable region (keyboard-scrollable in Firefox). CSS: `::placeholder` at AA contrast. Build clean; **re-tab through Profile once in the browser before the demo** | ✅ code |
| Screen-reader (audio-experience) pass: decorative symbols in chips/banners (✓ ✋ ⚠ ▲ ≤ ≈ ? 🤖 🔍) wrapped in `aria-hidden` spans across Profile/Understand/Prepare/Discover (adjacent text carries the meaning; SRs were speaking "black up-pointing triangle" etc.); stepper's CSS `✓` silenced via `content: "✓ " / ""` alt-text syntax (duplicated the hidden "(visited)" label); "Working…" no longer aria-hidden. App has no audio/video content → 1.2.x/1.4.2 pass vacuously; the demo video is the only captions surface (see user task 2). Build clean | ✅ code |
| Full a11y audit via claude-a11y-skill: **axe-core runtime scan = 0 violations across 9 real UI states** (consent→upload→zoom→correct→confirm-all→Q&A→delete-dialog→discover, driven by Playwright against the live app); jsx-a11y static scan clean (autoFocus replaced with pendingFocus; 2 justified inline suppressions). Report: `docs/accessibility-audit.md` (judge evidence); raw `frontend/axe-results.json`; rerun via `node frontend/axe-scan.mjs` (needs backend + vite dev up). New devDeps: eslint, eslint-plugin-jsx-a11y, typescript-eslint, playwright, axe-core (+ `eslint.a11y.mjs`). Gotcha discovered: `confirm-all` API 400s while any field is abstained — correct it first (the scan script does) | ✅ |

## What remains (user tasks)

1. ~~With-key verification~~ ✅ **DONE** — user's key is in `backend/.env` (gitignored; loaded via python-dotenv; template at `.env.example`) with `OPENAI_MODEL=gpt-5.4-nano`; `python scripts/test_llm_assist.py` → **LLM assist: ALL PASS** (paraphrase routing to correct rules, grounded plain_language, hostile prompts deflected).
2. **Rehearse + record the demo video** per `docs/demo-script.md` — now includes the abstention beat (step 1) and the AI beat (step 3, key required). **Add captions (or ship the transcript)** — the demo video is the only WCAG 1.2.2 surface. `docs/demo-transcript.md` is ready (narration + [actions], derived from the script — tweak lines after recording if you ad-lib, then link it in the submission next to the video). Even easier: YouTube auto-captions (fix "LIHTC"/"MTSP" in Studio) or Clipchamp's Autocaptions if recording there.
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
