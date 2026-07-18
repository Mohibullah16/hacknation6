"""Full-data API test: every household, end-to-end through the real API.

For each of the 6 households: create session -> upload its 4 PDFs -> confirm
all fields -> calculation -> compare annualized income / threshold /
comparison / readiness status / reason codes / missing-doc gaps against the
gold checklists -> export packet ZIP -> delete session.

Run from repo root:  python eval/api_full.py
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import CHECKLISTS_PATH, DOCUMENTS_DIR  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
CHECKLISTS = json.loads(CHECKLISTS_PATH.read_text(encoding="utf-8"))
FAILS: list[str] = []


def check(hh: str, name: str, cond: bool, note: str = ""):
    if not cond:
        FAILS.append(f"{hh} {name}: {note}")
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {note}" if note and not cond else ""))


for cl in CHECKLISTS:
    hh = cl["household_id"]
    num = hh.split("-")[1].lstrip("0").zfill(3)
    print(f"\n=== {hh} ({cl['scenario']}) ===")

    sid = client.post("/api/session", json={"consent": True}).json()["session_id"]

    files = sorted(DOCUMENTS_DIR.glob(f"hh-{hh[3:]}_*.pdf"))
    check(hh, "4 fixture files found", len(files) == 4, str([f.name for f in files]))
    for f in files:
        with f.open("rb") as fh:
            r = client.post(f"/api/session/{sid}/documents", files={"file": (f.name, fh, "application/pdf")})
        check(hh, f"upload {f.name}", r.status_code == 200, r.text[:120])

    state = client.get(f"/api/session/{sid}").json()
    for d in state["documents"]:
        r = client.post(f"/api/session/{sid}/documents/{d['document_id']}/confirm-all")
        check(hh, f"confirm-all {d['document_id']}", r.status_code == 200, r.text[:120])

    r = client.get(f"/api/session/{sid}/calculation").json()
    check(hh, "calculation unlocked", r["status"] == "ok", str(r)[:150])
    if r["status"] != "ok":
        client.delete(f"/api/session/{sid}")
        continue
    calc, readiness = r["calc"], r["readiness"]

    check(
        hh,
        f"annualized {cl['expected_annualized_income']}",
        abs(calc["annualized_income"] - cl["expected_annualized_income"]) < 0.005,
        f"got {calc['annualized_income']}",
    )
    check(
        hh,
        f"threshold {cl['frozen_60_percent_threshold']}",
        calc["threshold"] == cl["frozen_60_percent_threshold"],
        f"got {calc['threshold']}",
    )
    check(hh, f"comparison {cl['comparison']}", calc["comparison"] == cl["comparison"], f"got {calc['comparison']}")
    check(
        hh,
        f"readiness {cl['expected_readiness_status']}",
        readiness["readiness_status"] == cl["expected_readiness_status"],
        f"got {readiness['readiness_status']}",
    )
    got_codes = sorted(x["code"] for x in readiness["reasons"])
    check(hh, f"reasons {cl['expected_review_reasons']}", got_codes == sorted(cl["expected_review_reasons"]), f"got {got_codes}")
    got_missing = sorted(g["document_type"] for g in readiness["checklist_gaps"] if g["status"] == "missing")
    check(hh, f"missing-doc gaps {cl['missing_document_types']}", got_missing == sorted(cl["missing_document_types"]), f"got {got_missing}")
    check(hh, "effective date 2026-05-01", calc["threshold_effective_date"] == "2026-05-01", str(calc["threshold_effective_date"]))

    r = client.get(f"/api/session/{sid}/packet/export")
    ok_zip = r.status_code == 200
    if ok_zip:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        sub = json.loads(z.read("submission.json"))
        ok_zip = (
            sub["household_id"] == hh
            and sub["readiness_status"] == cl["expected_readiness_status"]
            and abs(sub["annualized_income"] - cl["expected_annualized_income"]) < 0.005
            and len(sub["citations"]) > 0
            and "eligib" not in json.dumps(sub).lower().replace("no eligibility determination", "")
        )
    check(hh, "packet ZIP + submission.json consistent", ok_zip)

    r = client.delete(f"/api/session/{sid}")
    check(hh, "session deleted", r.status_code == 200)

print("\n" + "=" * 50)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("ALL 6 HOUSEHOLDS PASS END-TO-END THROUGH THE API")
