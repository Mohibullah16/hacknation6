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
| confidence per field | Drives abstention (<0.60) and the renter-confirmation UI |
| adversarial_text_detected | Warns the renter that embedded instructions were found and ignored |

## Discover (stretch) — property display fields

hud_id, project_name, address/city/state/zip, unit counts by bedroom, geocode precision code (display precision caveat), availability (constant "unknown" — the dataset cannot support vacancy claims). Filters are renter-selected only (city, bedrooms); the unfiltered count is always shown; no record is ever hidden, ranked, or scored.

## Features deliberately absent

Race, ethnicity, national origin, immigration status, disability, health, religion, sex/gender, familial details beyond supplied household size, criminal/eviction history, credit signals, device/behavioral signals, landlord revenue optimization signals — none are collected, inferred, or used. Requests to infer them are refused (adversarial tests ADV-009/021).
