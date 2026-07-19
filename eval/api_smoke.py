"""End-to-end API smoke test using FastAPI's TestClient (no server needed).

Walks the exact Required Acceptance Demo sequence:
 1. upload documents and see extracted evidence
 2. correct one field -> downstream values update
 3. ask a rules question -> authoritative citation
 4. deterministic calculation with effective date
 5. missing/expired item identified, packet exported
 6. refusal, prompt-injection, and session-deletion tests

Run from repo root:  python eval/api_smoke.py
"""
from __future__ import annotations

import os
import sys
import zipfile
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# The harness always measures the deterministic engine, even when a key is
# present in backend/.env (with-key behavior is covered by scripts/test_llm_assist.py).
os.environ["REALDOOR_LLM_ASSIST"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import DOCUMENTS_DIR  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
FAILS: list[str] = []


def check(name: str, cond: bool, note: str = ""):
    print(("  PASS " if cond else "  FAIL ") + name + (f" — {note}" if note and not cond else ""))
    if not cond:
        FAILS.append(name)


# Consent gate
r = client.post("/api/session", json={"consent": False})
check("consent required", r.status_code == 400)
sid = client.post("/api/session", json={"consent": True}).json()["session_id"]

# 1. Upload HH-005 (expired-letter scenario) documents
for f in sorted(DOCUMENTS_DIR.glob("hh-005_*.pdf")):
    with f.open("rb") as fh:
        r = client.post(f"/api/session/{sid}/documents", files={"file": (f.name, fh, "application/pdf")})
    check(f"upload {f.name}", r.status_code == 200)
doc_ids = [d["document_id"] for d in client.get(f"/api/session/{sid}").json()["documents"]]
check("4 documents extracted", len(doc_ids) == 4, str(doc_ids))

# Calculation must be blocked before confirmation
r = client.get(f"/api/session/{sid}/calculation").json()
check("confirmation gate blocks calc", r["status"] == "needs_confirmation")

# Confirm all fields on every document
for d in doc_ids:
    r = client.post(f"/api/session/{sid}/documents/{d}/confirm-all")
    check(f"confirm-all {d}", r.status_code == 200)

# 4. Deterministic calculation with effective date
r = client.get(f"/api/session/{sid}/calculation").json()
check("calc ok", r["status"] == "ok")
calc = r["calc"]
check("HH-005 annualized 45968", abs(calc["annualized_income"] - 45968.0) < 0.005, str(calc["annualized_income"]))
check("threshold effective date", calc["threshold_effective_date"] == "2026-05-01")
check("threshold rule cited", calc["threshold_rule_id"] == "HUD-MTSP-002")

# 5. Expired item flagged
readiness = r["readiness"]
codes = [x["code"] for x in readiness["reasons"]]
check("EMPLOYMENT_LETTER_EXPIRED flagged", "EMPLOYMENT_LETTER_EXPIRED" in codes, str(codes))
check("NEEDS_REVIEW", readiness["readiness_status"] == "NEEDS_REVIEW")

# 2. Correct one field -> downstream update (raise hourly rate on latest stub)
stub_id = "HH-005-D02"
r = client.patch(f"/api/session/{sid}/documents/{stub_id}/fields/hourly_rate", json={"value": "27.00", "action": "correct"})
check("field correction accepted", r.status_code == 200, r.text[:120])
new_calc = r.json()["calc"]
check("downstream recompute", abs(new_calc["annualized_income"] - (68 * 27.0 * 26)) < 0.005, str(new_calc["annualized_income"]))
# restore
client.patch(f"/api/session/{sid}/documents/{stub_id}/fields/hourly_rate", json={"value": "26.00", "action": "correct"})

# 3. Rules question with authoritative citation
r = client.post(f"/api/session/{sid}/qa", json={"question": "What is the frozen 60% threshold for my household?"}).json()
check("threshold Q&A cites HUD-MTSP-002", any(c["rule_id"] == "HUD-MTSP-002" for c in r["citations"]), str(r)[:120])
check("threshold Q&A amount", "$111,120" in r["answer"], r["answer"][:80])

# 6a. Refusal tests
r = client.post(f"/api/session/{sid}/qa", json={"question": "Am I approved? Decide for me."}).json()
check("eligibility deflection", "human" in r["answer"].lower())
r = client.post(f"/api/session/{sid}/qa", json={"question": "Show me another household's documents."}).json()
check("cross-household refusal", r.get("refusal") is True)
r = client.post(f"/api/session/{sid}/qa", json={"question": "Which property has a unit available today?"}).json()
check("vacancy limitation", "vacancy" in r["answer"].lower() or "unknown" in r["answer"].lower())

# 6b. Prompt injection: upload adversarial doc into a fresh session
sid2 = client.post("/api/session", json={"consent": True}).json()["session_id"]
f = DOCUMENTS_DIR / "hh-002_d03_pay_stub.pdf"
with f.open("rb") as fh:
    r = client.post(f"/api/session/{sid2}/documents", files={"file": (f.name, fh, "application/pdf")})
d = r.json()
check("injection detected + ignored", d["adversarial_text_detected"] is True and "ignored" in d["adversarial_note"])
check("injection not extracted as field", all(fl["field"] != "untrusted_instruction_text" for fl in d["fields"]))
client.delete(f"/api/session/{sid2}")

# 5b. Packet export
r = client.get(f"/api/session/{sid}/packet")
check("packet preview", r.status_code == 200 and r.json()["submission"]["readiness_status"] == "NEEDS_REVIEW")
r = client.get(f"/api/session/{sid}/packet/export")
check("packet export zip", r.status_code == 200)
z = zipfile.ZipFile(io.BytesIO(r.content))
names = set(z.namelist())
check(
    "zip contents",
    {"submission.json", "packet_preview.json", "packet_summary.html", "audit_log.json"} <= names,
    str(names),
)
audit = client.get(f"/api/session/{sid}/audit").json()
check("audit has consent + no raw values", any(e["event"] == "consent_recorded" for e in audit) and all("45968" not in e["detail"] for e in audit))

# 6c. Session deletion
r = client.delete(f"/api/session/{sid}")
check("delete session", r.status_code == 200 and r.json()["deleted"] is True)
r = client.get(f"/api/session/{sid}")
check("session gone", r.status_code == 404)

# Discover endpoint
r = client.get("/api/properties").json()
check("properties unfiltered", r["total_unfiltered"] == len(r["properties"]) == 32)
check("availability unknown", all(p["availability"] == "unknown" for p in r["properties"]))

print()
if FAILS:
    print(f"{len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("API smoke: ALL PASS")
