"""RealDoor API — assistive application-readiness backend.

Boundaries enforced at this layer:
- Consent required before any upload (session creation records it).
- Extracted values must be renter-confirmed or corrected before they feed the
  deterministic calculation (confirmation gate).
- Every generated answer passes the decision-language output gate.
- Sessions are isolated and hard-deletable; nothing persists to disk.
"""
from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .config import FIELD_ALLOWLIST, LIHTC_CSV_PATH, OPENAI_MODEL, RULE_CORPUS_VERSION
from .extraction.parse import parse_field
from .extraction.pipeline import extract_document
from .household import build_household_result
from .llm import assist
from .privacy.packet import build_export_zip, packet_preview
from .privacy.store import STORE
from .rules.corpus import RULES, answer_question, build_intent_answer

app = FastAPI(title="RealDoor — Application-Readiness Copilot", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateSessionBody(BaseModel):
    consent: bool


class FieldUpdateBody(BaseModel):
    value: Optional[str | int | float] = None
    action: str  # "confirm" | "correct"


class QABody(BaseModel):
    question: str


def _session(session_id: str):
    s = STORE.get(session_id)
    if s is None:
        raise HTTPException(404, "Session not found (it may have been deleted or expired).")
    return s


def _recompute(s) -> None:
    """Recompute calc + readiness from confirmed/corrected fields only."""
    from .models import DocumentExtraction, FieldValue

    gated_docs = []
    for doc in s.documents.values():
        gated = DocumentExtraction(
            document_id=doc.document_id,
            household_id=doc.household_id,
            document_type=doc.document_type,
            file_name=doc.file_name,
            rasterized=doc.rasterized,
            adversarial_text_detected=doc.adversarial_text_detected,
            adversarial_note=doc.adversarial_note,
            fields=[f for f in doc.fields if f.status in ("confirmed", "corrected")],
        )
        gated_docs.append(gated)
    from .household import household_size_from_documents

    s.household_size = household_size_from_documents(gated_docs)
    calc, readiness, submission = build_household_result(
        s.household_id or "SESSION", gated_docs, s.household_size
    )
    s.calc, s.readiness = calc, readiness
    s.log("recomputed", f"annualized_income and readiness refreshed; rule_corpus={RULE_CORPUS_VERSION}")


def _unconfirmed_fields(s) -> list[dict]:
    out = []
    for doc in s.documents.values():
        for f in doc.fields:
            if f.status in ("extracted", "abstained"):
                out.append({"document_id": doc.document_id, "field": f.field, "status": f.status})
    return out


@app.get("/api/config")
def get_config():
    """Truthful disclosure for the consent screen: whether the optional OpenAI
    assist is active in this deployment, and which model it would use."""
    enabled = assist.assist_enabled()
    return {
        "llm_assist_enabled": enabled,
        "llm_explain_enabled": assist.explain_enabled(),
        "llm_crosscheck_enabled": assist.crosscheck_enabled(),
        "llm_model": OPENAI_MODEL if enabled else None,
        "rule_corpus_version": RULE_CORPUS_VERSION,
    }


@app.post("/api/session")
def create_session(body: CreateSessionBody):
    if not body.consent:
        raise HTTPException(400, "Consent is required before any document processing.")
    s = STORE.create(consent=True)
    return {"session_id": s.session_id, "rule_corpus_version": RULE_CORPUS_VERSION}


@app.get("/api/session/{sid}")
def get_session(sid: str):
    s = _session(sid)
    return {
        "session_id": s.session_id,
        "household_id": s.household_id,
        "household_size": s.household_size,
        "documents": [d.to_dict() for d in s.documents.values()],
        "unconfirmed_fields": _unconfirmed_fields(s),
        "calc": s.calc.to_dict() if s.calc else None,
        "readiness": s.readiness.to_dict() if s.readiness else None,
    }


@app.post("/api/session/{sid}/documents")
async def upload_document(sid: str, file: UploadFile):
    s = _session(sid)
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "File too large (5 MB limit for this prototype).")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF documents are supported.")
    # Keep the original filename (its stem is a type/type-detection fallback);
    # bytes only ever touch a per-request temp dir that is removed immediately.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / Path(file.filename).name
        tmp_path.write_bytes(data)
        doc = extract_document(tmp_path, fallback_document_id=Path(file.filename).stem)
    doc.file_name = file.filename
    if assist.crosscheck_enabled():
        # Advisory only (opt-in): notes for the renter to double-check; never
        # changes a value, a status, or the calculation.
        doc.advisory_flags = assist.crosscheck_fields(
            doc.document_type, [{"field": f.field, "value": f.value} for f in doc.fields]
        )
    s.documents[doc.document_id] = doc
    s.files[doc.document_id] = data
    if doc.household_id and not s.household_id:
        s.household_id = doc.household_id
    s.log(
        "document_uploaded",
        f"{doc.document_id} type={doc.document_type} rasterized={doc.rasterized} "
        f"fields={[f.field for f in doc.fields]} adversarial={doc.adversarial_text_detected}",
    )
    return doc.to_dict()


@app.get("/api/session/{sid}/documents/{doc_id}/file")
def get_document_file(sid: str, doc_id: str):
    s = _session(sid)
    data = s.files.get(doc_id)
    if data is None:
        raise HTTPException(404, "Document not found in this session.")
    return Response(content=data, media_type="application/pdf")


@app.patch("/api/session/{sid}/documents/{doc_id}/fields/{field_name}")
def update_field(sid: str, doc_id: str, field_name: str, body: FieldUpdateBody):
    s = _session(sid)
    doc = s.documents.get(doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found in this session.")
    fv = doc.get(field_name)
    if fv is None:
        raise HTTPException(404, "Field not found on this document.")
    if field_name not in FIELD_ALLOWLIST:
        raise HTTPException(400, "Field is not on the extraction allowlist.")
    if body.action == "confirm":
        if fv.value is None:
            raise HTTPException(400, "An abstained field must be corrected with a value, not confirmed.")
        fv.status = "confirmed"
        s.log("field_confirmed", f"{doc_id}:{field_name}")
    elif body.action == "correct":
        value, ok = parse_field(field_name, str(body.value))
        if not ok:
            raise HTTPException(422, f"'{body.value}' is not a valid value for {field_name}.")
        fv.value = value
        fv.status = "corrected"
        fv.confidence = 1.0
        s.log("field_corrected", f"{doc_id}:{field_name} (value updated by renter)")
    else:
        raise HTTPException(400, "action must be 'confirm' or 'correct'.")
    _recompute(s)
    return {
        "field": {"field": fv.field, "value": fv.value, "status": fv.status, "confidence": fv.confidence},
        "calc": s.calc.to_dict() if s.calc else None,
        "readiness": s.readiness.to_dict() if s.readiness else None,
        "unconfirmed_fields": _unconfirmed_fields(s),
    }


@app.post("/api/session/{sid}/documents/{doc_id}/confirm-all")
def confirm_all(sid: str, doc_id: str):
    s = _session(sid)
    doc = s.documents.get(doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found in this session.")
    blocked = [f.field for f in doc.fields if f.status == "abstained"]
    if blocked:
        raise HTTPException(400, f"These fields were abstained and need manual correction first: {blocked}")
    for f in doc.fields:
        if f.status == "extracted":
            f.status = "confirmed"
    s.log("fields_confirmed_bulk", f"{doc_id}: all extracted fields confirmed by renter")
    _recompute(s)
    return get_session(sid)


@app.get("/api/session/{sid}/calculation")
def get_calculation(sid: str):
    s = _session(sid)
    unconfirmed = _unconfirmed_fields(s)
    if unconfirmed:
        return {
            "status": "needs_confirmation",
            "message": "Confirm or correct every extracted value before calculation — the renter, not the model, owns the profile.",
            "unconfirmed_fields": unconfirmed,
        }
    if s.calc is None:
        _recompute(s)
    return {
        "status": "ok",
        "calc": s.calc.to_dict(),
        "readiness": s.readiness.to_dict(),
    }


# Safety/refusal templates are shown verbatim — never rephrased by the LLM.
_NO_REPHRASE_RULE_IDS = {"CH-DECISION-001", "CH-SAFETY-001"}


@app.post("/api/session/{sid}/qa")
def rules_qa(sid: str, body: QABody):
    """Q&A pipeline: deterministic keyword router first (always). If it
    abstains and the optional OpenAI assist is enabled, the LLM may only
    *classify* the question into a vetted intent — the answer text and citation
    still come from the deterministic builders. LLM-generated text appears
    solely in the supplementary `plain_language` field, which is discarded
    unless it passes the decision-language gate and number-grounding check
    (both enforced inside `assist.plain_language`)."""
    s = _session(sid)
    ans = answer_question(body.question, s)
    ans["assist_used"] = False

    if ans.get("abstained") and assist.assist_enabled():
        intent = assist.route_question(body.question)
        routed = build_intent_answer(intent, s) if intent else None
        if routed is not None:
            ans = routed
            ans["assist_used"] = True

    cited_ids = {c.get("rule_id") for c in ans["citations"]}
    if (
        assist.explain_enabled()
        and not ans.get("abstained")
        and not ans.get("refusal")
        and not (cited_ids & _NO_REPHRASE_RULE_IDS)
    ):
        plain = assist.plain_language(body.question, ans["answer"], ans["citations"])
        if plain:
            ans["plain_language"] = plain

    s.log(
        "rules_question_answered",
        f"cited={sorted(str(c) for c in cited_ids)} abstained={ans.get('abstained')} "
        f"assist_used={ans.get('assist_used')}",
    )
    return ans


@app.get("/api/session/{sid}/packet")
def get_packet(sid: str):
    s = _session(sid)
    if _unconfirmed_fields(s):
        raise HTTPException(409, "Confirm or correct all extracted values before building the packet.")
    if s.calc is None:
        _recompute(s)
    _, _, submission = _submission(s)
    s.log("packet_previewed", "renter previewed packet")
    return packet_preview(s, submission)


@app.get("/api/session/{sid}/packet/export")
def export_packet(sid: str):
    s = _session(sid)
    if _unconfirmed_fields(s):
        raise HTTPException(409, "Confirm or correct all extracted values before exporting the packet.")
    if s.calc is None:
        _recompute(s)
    _, _, submission = _submission(s)
    data = build_export_zip(s, submission)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="readiness-packet-{s.household_id or s.session_id[:8]}.zip"'},
    )


def _submission(s):
    from .models import DocumentExtraction

    gated_docs = [
        DocumentExtraction(
            document_id=d.document_id,
            household_id=d.household_id,
            document_type=d.document_type,
            file_name=d.file_name,
            rasterized=d.rasterized,
            adversarial_text_detected=d.adversarial_text_detected,
            adversarial_note=d.adversarial_note,
            fields=[f for f in d.fields if f.status in ("confirmed", "corrected")],
        )
        for d in s.documents.values()
    ]
    return build_household_result(s.household_id or "SESSION", gated_docs, s.household_size)


@app.get("/api/session/{sid}/audit")
def get_audit(sid: str):
    s = _session(sid)
    return [{"ts": e.ts, "event": e.event, "detail": e.detail} for e in s.audit]


@app.delete("/api/session/{sid}")
def delete_session(sid: str):
    ok = STORE.delete(sid)
    if not ok:
        raise HTTPException(404, "Session not found (already deleted or expired).")
    return {"deleted": True, "message": "All session data — uploads, extracted values, results — has been erased from memory."}


@app.get("/api/rules")
def list_rules():
    return list(RULES.values())


@app.get("/api/properties")
def list_properties():
    """Discover (stretch): full unfiltered LIHTC teaching subset. Availability
    is always unknown — this dataset cannot support vacancy claims (HUD-DATA-001)."""
    rows = []
    with LIHTC_CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            row["availability"] = "unknown"
            rows.append(row)
    return {
        "disclaimer": RULES["HUD-DATA-001"]["text"],
        "total_unfiltered": len(rows),
        "properties": rows,
    }
