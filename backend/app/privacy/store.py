"""In-memory, session-scoped storage with audit logging and hard deletion.

Privacy posture:
- Nothing is written to disk. Uploaded bytes and extracted values live only in
  process memory, scoped to a session UUID, and are purged on delete or TTL.
- The audit log records events, actors, field names, and rule-corpus versions —
  never raw document contents or extracted values.
- Cross-session access is impossible by construction (lookup by session id
  only; no listing endpoint exposes other sessions' data).
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..config import RULE_CORPUS_VERSION
from ..models import CalcResult, DocumentExtraction, ReadinessResult

SESSION_TTL_SECONDS = 4 * 60 * 60


@dataclass
class AuditEvent:
    ts: float
    event: str
    detail: str  # field names / document ids / rule ids only — never values


@dataclass
class Session:
    session_id: str
    created_at: float
    consent: bool = False
    documents: dict[str, DocumentExtraction] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)  # doc_id -> pdf bytes
    household_id: str = ""
    household_size: Optional[int] = None
    calc: Optional[CalcResult] = None
    readiness: Optional[ReadinessResult] = None
    audit: list[AuditEvent] = field(default_factory=list)

    def log(self, event: str, detail: str = "") -> None:
        self.audit.append(AuditEvent(ts=time.time(), event=event, detail=detail))


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, consent: bool) -> Session:
        sid = str(uuid.uuid4())
        s = Session(session_id=sid, created_at=time.time(), consent=consent)
        s.log("session_created", f"rule_corpus={RULE_CORPUS_VERSION}")
        s.log("consent_recorded", "renter consented to allowlisted-field extraction for readiness preparation")
        with self._lock:
            self._purge_expired()
            self._sessions[sid] = s
        return s

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            self._purge_expired()
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            s = self._sessions.pop(session_id, None)
        if s is not None:
            # Explicitly drop references to uploaded bytes and values.
            s.files.clear()
            s.documents.clear()
            return True
        return False

    def _purge_expired(self) -> None:
        now = time.time()
        for sid in [k for k, v in self._sessions.items() if now - v.created_at > SESSION_TTL_SECONDS]:
            s = self._sessions.pop(sid)
            s.files.clear()
            s.documents.clear()


STORE = SessionStore()
