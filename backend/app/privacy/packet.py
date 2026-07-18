"""Renter-controlled packet builder.

The packet is assembled only on explicit renter request, previewed in the UI,
and downloaded locally as a ZIP. Nothing is ever transmitted to a property,
provider, or third party.
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from html import escape

from ..config import CURRENCY_WINDOW_DAYS, EVENT_DATE, RULE_CORPUS_VERSION
from .store import Session

DISCLAIMER = (
    "This packet is an application-readiness summary prepared and controlled by the renter. "
    "It contains no eligibility, approval, denial, priority, or availability determination. "
    "A qualified human reviewer at the housing program makes any determination."
)


def packet_preview(session: Session, submission: dict) -> dict:
    docs = []
    for doc in session.documents.values():
        docs.append(
            {
                "document_id": doc.document_id,
                "document_type": doc.document_type,
                "file_name": doc.file_name,
                "adversarial_text_detected": doc.adversarial_text_detected,
                "fields": [
                    {
                        "field": f.field,
                        "value": f.value,
                        "status": f.status,
                        "confidence": f.confidence,
                        "page": f.page,
                        "bbox": f.bbox,
                    }
                    for f in doc.fields
                ],
            }
        )
    return {
        "disclaimer": DISCLAIMER,
        "rule_corpus_version": RULE_CORPUS_VERSION,
        "event_date": EVENT_DATE.isoformat(),
        "currency_window_days": CURRENCY_WINDOW_DAYS,
        "household_id": session.household_id,
        "household_size": session.household_size,
        "documents": docs,
        "calculation": session.calc.to_dict() if session.calc else None,
        "readiness": session.readiness.to_dict() if session.readiness else None,
        "submission": submission,
    }


def packet_summary_html(preview: dict) -> str:
    """Printable, accessible standalone summary included in the export ZIP."""
    calc = preview.get("calculation") or {}
    readiness = preview.get("readiness") or {}
    rows = []
    for doc in preview["documents"]:
        for f in doc["fields"]:
            rows.append(
                f"<tr><td>{escape(doc['document_id'])}</td><td>{escape(f['field'])}</td>"
                f"<td>{escape(str(f['value']))}</td><td>{escape(f['status'])}</td>"
                f"<td>p.{f['page']}, box {f['bbox']}</td></tr>"
            )
    reasons = "".join(
        f"<li><strong>{escape(r['code'])}</strong> — {escape(r['detail'])} (rule {escape(r['rule_id'])})</li>"
        for r in readiness.get("reasons", [])
    ) or "<li>None — all readiness checks passed.</li>"
    gaps = "".join(
        f"<li>{escape(g['document_type'])} ({escape(g['status'])}): {escape(g['guidance'])}</li>"
        for g in readiness.get("checklist_gaps", [])
    ) or "<li>No checklist gaps.</li>"
    sources = "".join(
        f"<li>{escape(s['source_type'])} ({escape(s['document_id'])}): {escape(s['formula'])}</li>"
        for s in calc.get("sources", [])
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Application-readiness packet — {escape(preview.get('household_id') or 'household')}</title>
<style>
 body {{ font-family: Georgia, serif; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; color: #1a1a2e; }}
 h1, h2 {{ font-family: Arial, sans-serif; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #888; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
 .banner {{ border: 2px solid #1d4ed8; background: #eff6ff; padding: 0.8rem 1rem; }}
</style>
</head>
<body>
<h1>Application-readiness packet</h1>
<p class="banner"><strong>Human decision boundary:</strong> {escape(preview['disclaimer'])}</p>
<h2>Deterministic calculation</h2>
<p>Annualized documented recurring gross income: <strong>${calc.get('annualized_income', 0):,.2f}</strong></p>
<p>Formula: {escape(calc.get('formula', ''))}</p>
<ul>{sources}</ul>
<p>Frozen 60% MTSP threshold (household size {preview.get('household_size')}):
<strong>${(calc.get('threshold') or 0):,.0f}</strong>, effective {escape(str(calc.get('threshold_effective_date')))},
rule {escape(str(calc.get('threshold_rule_id')))} — comparison: <strong>{escape(str(calc.get('comparison')))}</strong>.</p>
<h2>Readiness</h2>
<p>Status: <strong>{escape(str(readiness.get('readiness_status')))}</strong> (document-readiness signal, not a decision)</p>
<h3>Reasons</h3><ul>{reasons}</ul>
<h3>Checklist gaps</h3><ul>{gaps}</ul>
<h2>Confirmed evidence</h2>
<table>
<caption>Every value with its source citation</caption>
<thead><tr><th scope="col">Document</th><th scope="col">Field</th><th scope="col">Value</th><th scope="col">Status</th><th scope="col">Citation</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p>Rule corpus version: {escape(preview['rule_corpus_version'])} · Generated for the frozen event date {escape(preview['event_date'])} ·
Document-currency convention: {preview['currency_window_days']} days (simulation convention, not a universal LIHTC rule).</p>
</body>
</html>"""


def build_export_zip(session: Session, submission: dict) -> bytes:
    preview = packet_preview(session, submission)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("submission.json", json.dumps(submission, indent=2))
        z.writestr("packet_preview.json", json.dumps(preview, indent=2))
        z.writestr("packet_summary.html", packet_summary_html(preview))
        z.writestr(
            "audit_log.json",
            json.dumps(
                [{"ts": e.ts, "event": e.event, "detail": e.detail} for e in session.audit],
                indent=2,
            ),
        )
        for doc_id, data in session.files.items():
            doc = session.documents.get(doc_id)
            name = doc.file_name if doc else f"{doc_id}.pdf"
            z.writestr(f"documents/{name}", data)
    session.log("packet_exported", f"{len(session.files)} document(s), local download only")
    return buf.getvalue()
