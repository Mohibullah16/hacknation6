"""Generate the demo-only degraded pay stub used for the abstention beat.

Writes  realdoor/demo/demo_pay_stub_lowquality.pdf  — a synthetic HH-005 pay
stub whose HOURLY RATE prints as an illegible scan artifact ("2S.G0"), so the
extractor abstains on that one field (parse fails -> confidence 0.485 < 0.60)
and the renter must type the value. Every other field extracts normally.

Design constraints (do not break these):
- Lives in demo/, NOT pack_data/ — eval/api_smoke.py globs hh-005_*.pdf and
  asserts exactly 4 documents, and run_eval.py iterates gold docs only.
- pay_date 2026-06-13: older than HH-005-D02 (2026-06-27) so the latest-stub
  rule ignores this stub in the income calc, but inside the 60-day currency
  window (cutoff 2026-05-19) so it never adds a spurious EXPIRED flag.
- Values internally consistent (68 h x $26.00 = $1,768.00) so after the renter
  corrects the rate, no PAY_STUB_TOTAL_CONFLICT can appear.

Run from repo root:  python scripts/make_demo_doc.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo" / "demo_pay_stub_lowquality.pdf"

# (x, baseline_y, font_size, gray_level, text)
TEXTS = [
    (50, 750, 16, 0.0, "Pay Stub"),
    (50, 728, 10, 0.0, "Harborline Logistics - Payroll Statement (SYNTHETIC DEMO DOCUMENT)"),
    (50, 714, 9, 0.3, "Document HH-005-D05 - low-quality scan for the abstention demo"),
    # Row A
    (50, 680, 10, 0.0, "EMPLOYEE"),
    (250, 680, 10, 0.0, "PAY DATE"),
    (420, 680, 10, 0.0, "PAY FREQUENCY"),
    (50, 664, 10, 0.0, "Tess Alder"),
    (250, 664, 10, 0.0, "2026-06-13"),
    (420, 664, 10, 0.0, "biweekly"),
    # Row B
    (50, 630, 10, 0.0, "PAY PERIOD"),
    (250, 630, 10, 0.0, "THROUGH"),
    (50, 614, 10, 0.0, "2026-05-27"),
    (250, 614, 10, 0.0, "2026-06-09"),
    # Row C — HOURLY RATE value is the deliberate scan artifact (gray, garbled)
    (50, 580, 10, 0.0, "REGULAR HOURS"),
    (250, 580, 10, 0.0, "HOURLY RATE"),
    (420, 580, 10, 0.0, "GROSS PAY"),
    (50, 564, 10, 0.0, "68"),
    (250, 564, 10, 0.55, "2S.G0"),
    (420, 564, 10, 0.0, "1,768.00"),
    # Row D
    (50, 530, 10, 0.0, "NET PAY"),
    (50, 514, 10, 0.0, "1,379.04"),
]


def content_stream() -> bytes:
    parts = []
    for x, y, size, gray, text in TEXTS:
        esc = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        parts.append(f"{gray:.2f} g BT /F1 {size} Tf {x} {y} Td ({esc}) Tj ET")
    return ("\n".join(parts) + "\n").encode("latin-1")


def build_pdf() -> bytes:
    stream = content_stream()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build_pdf())
    print(f"wrote {OUT}")

    # Self-verify through the real pipeline.
    sys.path.insert(0, str(ROOT / "backend"))
    from app.extraction.pipeline import extract_document

    doc = extract_document(OUT)
    print(f"document_id={doc.document_id} household={doc.household_id} type={doc.document_type} rasterized={doc.rasterized}")
    failures = []
    expect_ok = {
        "person_name": "Tess Alder",
        "pay_date": "2026-06-13",
        "pay_frequency": "biweekly",
        "pay_period_start": "2026-05-27",
        "pay_period_end": "2026-06-09",
        "regular_hours": 68,
        "gross_pay": 1768,
        "net_pay": 1379.04,
    }
    for f in doc.fields:
        print(f"  {f.field:18s} status={f.status:9s} value={f.value!r} conf={f.confidence}")
    for name, want in expect_ok.items():
        fv = doc.get(name)
        if fv is None or fv.status != "extracted" or fv.value != want:
            failures.append(f"{name}: expected extracted {want!r}, got {fv and (fv.status, fv.value)}")
    rate = doc.get("hourly_rate")
    if rate is None or rate.status != "abstained" or rate.value is not None:
        failures.append(f"hourly_rate: expected abstained/None, got {rate and (rate.status, rate.value)}")
    if doc.document_type != "pay_stub":
        failures.append(f"type: {doc.document_type}")
    if doc.household_id != "HH-005":
        failures.append(f"household: {doc.household_id}")
    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("OK: hourly_rate abstains; all other fields extract cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
