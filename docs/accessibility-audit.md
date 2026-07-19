# Accessibility Audit Results

**Scan mode:** full (static + runtime)
**Standards:** WCAG 2.1 Level A + AA (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`) + axe best practices
**Date:** 2026-07-19
**Tools:** axe-core 4.x (Playwright/Chromium, against the live dev app) · eslint-plugin-jsx-a11y (recommended ruleset)

The runtime scan does not test static routes only — it drives the **real user journey** (consent → upload of the degraded demo pay stub → evidence zoom → correction of the abstained field → confirm-all → rules Q&A → readiness/packet → delete confirmation dialog → Discover) and runs axe on each meaningful UI state.

## Runtime results (axe-core)

| UI state | Violations | Passes | Incomplete |
|---|---|---|---|
| `/` (landing, pre-consent) | 0 | 46 | 0 |
| `/profile` (empty) | 0 | 39 | 0 |
| `/profile` (document uploaded) | 0 | 48 | 0 |
| `/profile` (evidence zoomed 2×) | 0 | 49 | 0 |
| `/profile` (all confirmed) | 0 | 50 | 1* |
| `/understand` (calc + cited answer) | 0 | 48 | 0 |
| `/prepare` (readiness + packet) | 0 | 40 | 0 |
| `/prepare` (delete alertdialog open) | 0 | 41 | 0 |
| `/discover` (filtered table) | 0 | 46 | 1* |

**Total: 0 violations across 9 states.**

\* The two "incomplete" entries are axe declining to compute color-contrast on the decorative `<span aria-hidden="true">✓ </span>` symbol spans ("element content contains only non-text characters"). These are intentionally hidden from assistive technology; the adjacent visible chip text passes contrast.

Raw output: `frontend/axe-results.json`. Reproduce with backend + `npm run dev` running, then `node frontend/axe-scan.mjs`.

## Static results (eslint-plugin-jsx-a11y)

`npx eslint --config eslint.a11y.mjs src/` → **clean** (exit 0).

Two rules are suppressed inline with justification comments:

- `no-noninteractive-tabindex` on the evidence viewer's scroll stage — axe's own `scrollable-region-focusable` rule *requires* `tabindex="0"` on keyboard-scrollable regions (WCAG 2.1.1); the jsx-a11y rule doesn't model scroll containers.
- `no-noninteractive-element-interactions` on the delete `alertdialog` — Escape handling and Tab-trapping on the dialog container is the WAI-ARIA modal dialog pattern.

One genuine finding was fixed rather than suppressed: `no-autofocus` on the inline correction input — replaced with explicit post-render focus management.

## Manual focus-management audit (beyond what scanners catch)

Automated tools cannot detect focus loss after DOM updates. A manual keyboard pass found and fixed:

- **Profile:** Confirm/Save/Cancel/Confirm-all disabled or unmounted the pressed button, dropping focus to `<body>` (re-tab from page top). Now: after Confirm, focus lands on the **next unconfirmed row's field/zoom button** (inspect the cited source box, then Tab to Confirm); after Save/Cancel, back on that row's Correct button; when the document completes, on the status banner containing the Step 2 link.
- **Understand:** focus lands on the answer region when an answer arrives; back in the input on error.
- **Prepare:** delete `alertdialog` traps Tab between its two actions, Escape cancels and returns focus to the trigger; after deletion focus lands on the confirmation heading; the timed auto-redirect was removed (WCAG 2.2.1).
- **App shell:** route changes move focus to `<main>` (skipped on initial load so the skip link stays first).

## Audio accessibility

The app contains no audio or video content, so WCAG 1.2.x (captions/audio description) and 1.4.2 (audio control) are satisfied vacuously. The spoken (screen-reader) experience was audited separately: decorative symbols (✓ ✋ ⚠ ▲ ≤ ≈ 🤖 🔍) are `aria-hidden` so they are not read as noise; the stepper's CSS-generated check is silenced via the `content` alt-text syntax; all state changes are announced through a polite live region. The demo video must ship with captions or the demo script as a transcript (WCAG 1.2.2) — it is the project's only audio surface.

## Summary

- Total violations: **0** (runtime) · **0** (static, after 1 fix + 2 justified suppressions)
- Critical: 0 | Serious: 0 | Moderate: 0 | Minor: 0
- Recommendation: keep `node frontend/axe-scan.mjs` in the pre-demo checklist; caption the demo video.
