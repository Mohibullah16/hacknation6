# Feature Manifest — every feature and its purpose

_Published per the challenge's "No hidden proxies" requirement: every feature the system uses, and why. There are no demographic, behavioral, or landlord-revenue features anywhere in the system, and no feature below is ever used to score, rank, or filter a person._

## Extracted document fields (the complete allowlist)

| Feature | Documents | Sole purpose |
|---|---|---|
| person_name | all | Group documents belonging to one household; never matched against external data |
| household_size | application summary | Select the frozen 60% MTSP row (sizes 1–8) |
| address | application summary | Display back to the renter for confirmation; not used in any computation |
| application_date | application summary | Display/context only |
| pay_date, pay_period_start, pay_period_end | pay stub | Pick the most recent stub; display the covered period |
| pay_frequency | pay stub | Annualization multiplier (weekly 52 · biweekly 26 · semimonthly 24 · monthly 12 · annual 1) |
| regular_hours, hourly_rate (+ overtime fields if present) | pay stub | Recompute component gross = hours × rate; authoritative over a conflicting displayed total |
| gross_pay | pay stub | Documented gross per period; cross-checked against components (conflict ⇒ NEEDS_REVIEW) |
| net_pay | pay stub | Display only; never used in the income calculation |
| document_date | employment/benefit letter | 60-day currency convention check (simulation convention) |
| weekly_hours | employment letter | Corroborates stub hours; never adds income |
| monthly_benefit, benefit_frequency | benefit letter | Annualize documented recurring benefit income |
| statement_month, gross_receipts | gig statement | Annualize documented recurring gig income (gross; corroboration required for readiness) |
| platform_fees | gig statement | Display only; fees are not deducted from gross income |

## Derived values

| Feature | Purpose |
|---|---|
| annualized_income | Sum of independently documented recurring gross sources |
| comparison (below_or_equal / above / no_frozen_threshold) | Numerical relation to the frozen threshold — explicitly **not** an eligibility conclusion |
| readiness_status + reason codes | Tells a **human reviewer** whether the packet is complete/consistent; missing docs are informational gaps, not automatic blockers |
| confidence per field | Extraction-path signal (digital text 0.97 · OCR ≤0.85 scaled by OCR score · halved when the value fails its type parser) — not a calibrated probability. Drives hard abstention (<0.60) and the renter-confirmation UI |
| adversarial_text_detected | Warns the renter that embedded instructions were found and ignored |

## Optional OpenAI assist (disclosed at consent; inactive without an API key)

| Data sent to OpenAI | When | Sole purpose |
|---|---|---|
| The renter's typed rules question | Only when the deterministic keyword router abstains | Classify the question into one vetted intent from a fixed enum (validated server-side); the answer text and citation always come from the local frozen corpus |
| The deterministic answer + its citation + the question | After a factual (never refusal/safety) answer | Produce a plain-language rephrasing shown *beside* the authoritative answer; discarded unless it passes the decision-language deny gate and introduces no new numbers |
| Allowlisted extracted field names/values (synthetic documents) | **Only** with the separate opt-in cross-check flag (off by default) | Advisory "double-check this value" notes; never changes a value, a status, or the calculation |

Nothing else is ever sent: no documents, no full document text, and no identity data beyond what appears in a typed question or — with the opt-in flag only — the allowlisted field values in the table above. OpenAI does not train on API data. No LLM output can become a number, threshold, status, or decision.

## Discover (stretch) — property display fields

hud_id, project_name, address/city/state/zip, unit counts by bedroom, geocode precision code (display precision caveat), availability (constant "unknown" — the dataset cannot support vacancy claims). Filters are renter-selected only (city, bedrooms); the unfiltered count is always shown; no record is ever hidden, ranked, or scored.

## Features deliberately absent

Race, ethnicity, national origin, immigration status, disability, health, religion, sex/gender, familial details beyond supplied household size, criminal/eviction history, credit signals, device/behavioral signals, landlord revenue optimization signals — none are collected, inferred, or used. Requests to infer them are refused (adversarial tests ADV-009/021).
