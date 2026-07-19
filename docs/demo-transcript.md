# Demo Video Transcript — RealDoor

_Text alternative for the demo video (WCAG 1.2.2). Spoken narration is in plain text; on-screen actions are in [brackets]. If the recorded narration deviates from this script, update the matching lines after recording._

---

RealDoor is assistive, not adjudicative — the AI extracts, explains, calculates and prepares; the renter confirms; a qualified human decides.

## 1 — Upload and extracted evidence

[Landing page] Before anything starts, the data-use table explains every field we read and why, and the AI-disclosure banner states whether a third-party model is active in this deployment — disclosed before consent. Documents are never sent anywhere. [Ticks the consent checkbox, clicks "Start my session"]

[Uploads the four HH-005 documents] Every extracted value appears with its confidence and waits for my confirmation. [Clicks a field name] Clicking a field highlights and zooms to the exact source box on the document — two of these documents are scanned images read by local OCR, same coordinate system.

[Uploads the degraded demo pay stub] This scan's hourly rate is illegible. The copilot abstains — "needs your entry", confidence forty-nine percent — instead of guessing. [Clicks "Confirm all"] Confirm-all correctly refuses until the abstained value is corrected. [Corrects it to 26.00] Below sixty percent confidence the tool never guesses — the renter supplies the value. And the income doesn't move, because the deterministic engine only ever uses the latest pay stub.

## 2 — Correct a field, watch downstream values update

[Confirms all values on each document] Nothing is used until I confirm it. The status banner flips to "Profile confirmed".

[On pay stub HH-005-D02, corrects hourly rate from 26.00 to 27.00] [Opens Understand] Annualized income now reads $47,736 — sixty-eight hours times twenty-seven dollars times twenty-six pay periods. One correction, everything recomputed deterministically. [Corrects it back; income returns to $45,968]

## 3 — Rules question with authoritative citation

[Clicks the suggested question "What is the frozen 60% threshold for my household?"] The answer is $111,120 for a household of five, cited to rule HUD-MTSP-002, effective May 1st 2026, with a link to the official HUD FY-26 report.

[With AI assist enabled — clicks "Do I earn too much for this program?"] That's a paraphrase no keyword list needs to anticipate. The AI only matched my wording to the frozen rule and rephrased the cited answer — it's checked so it can't add a single new number; every figure still comes from the deterministic engine. [Types an out-of-corpus question] And when the corpus doesn't cover something, it abstains rather than guessing.

[Asks "Am I eligible?"] Eligibility is deflected to rule plus input plus calculation and a human decision — a vetted template the AI is never allowed to rephrase.

## 4 — Deterministic calculation with effective date

[Scrolls the income-sources table] The formula is visible arithmetic: sixty-eight hours times twenty-six dollars is $1,768 biweekly, times twenty-six is $45,968 a year. The threshold row shows the rule id, its effective date, and the official source link. The comparison chip says "at or below the frozen threshold" — a numerical comparison only.

## 5 — Missing or expired items, then export

[Opens Prepare] Readiness shows NEEDS_REVIEW with the reason "employment letter expired" — the letter is older than the sixty-day convention, which is labeled as a simulation convention, not a real LIHTC rule, with guidance to request a fresh letter.

[Opens the packet preview, clicks "Download my packet"] The ZIP contains the schema-conformant submission JSON, a printable summary, the audit log, and my documents. Download only — there is no send-to-anyone button in this product.

## 6 — Refusal, prompt injection, and deletion

[Asks "Just approve me — decide for me"] Deflected, with the CH-DECISION-001 citation. [Asks "Which property has a unit available today?"] Deflected with the dataset limitation — this data cannot support vacancy claims.

[Uploads the injection test document] An amber banner: "Untrusted content ignored" — the document contained embedded instructions to reveal the system prompt, which were detected and ignored; none of it reaches the extracted fields.

[In Prepare, shows the audit log, then clicks "Delete my session and all data" and confirms] Events only, no values, in the log — and deletion erases everything from memory immediately; the stepper disappears and no page shows any data.

## Closing

Our local reproduction of the pack's extraction, calculation, readiness, citation, and adversarial checks scores one hundred percent — run `python eval/run_eval.py` offline to reproduce it. Every scored number is deterministic; the AI explains, the renter confirms, and a qualified human decides.
