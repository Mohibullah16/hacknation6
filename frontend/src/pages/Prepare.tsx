import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type ReadinessResult } from "../api";
import { useSession } from "../context";

interface PacketPreview {
  disclaimer: string;
  rule_corpus_version: string;
  household_id: string;
  readiness: ReadinessResult;
  [k: string]: unknown;
}

export default function Prepare() {
  const { sessionId, session, announce, clear } = useSession();
  const [packet, setPacket] = useState<PacketPreview | null>(null);
  const [audit, setAudit] = useState<{ ts: number; event: string; detail: string }[]>([]);
  const [error, setError] = useState("");
  const [deleted, setDeleted] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const navigate = useNavigate();
  const deleteTriggerRef = useRef<HTMLButtonElement>(null);
  const confirmDeleteRef = useRef<HTMLButtonElement>(null);

  /* Dialog focus management (WCAG 2.4.3): entering the confirm dialog moves
     focus to its first action; cancelling returns focus to the trigger. */
  useEffect(() => {
    if (confirmingDelete) confirmDeleteRef.current?.focus();
  }, [confirmingDelete]);

  function cancelDelete() {
    setConfirmingDelete(false);
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0);
  }

  useEffect(() => {
    if (!sessionId) return;
    api
      .getPacket(sessionId)
      .then((p) => setPacket(p as unknown as PacketPreview))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not build the packet preview."));
    api.getAudit(sessionId).then(setAudit).catch(() => undefined);
  }, [sessionId, session]);

  async function onDelete() {
    if (!sessionId) return;
    try {
      const r = await api.deleteSession(sessionId);
      setDeleted(r.message);
      announce(`Session deleted. ${r.message}`);
      clear();
      window.setTimeout(() => navigate("/"), 4000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Delete failed.";
      setError(msg);
      announce(`Error: ${msg}`);
    }
  }

  if (deleted) {
    return (
      <>
        <h1>Session deleted</h1>
        <p className="banner" role="status">
          ✓ {deleted} You will be returned to the start page shortly, or{" "}
          <Link to="/">go there now</Link>.
        </p>
      </>
    );
  }

  if (!sessionId) {
    return (
      <>
        <h1>Step 3 · Prepare</h1>
        <p>
          No active session. Please <Link to="/">start a session</Link> first.
        </p>
      </>
    );
  }

  const readiness = packet?.readiness;

  return (
    <>
      <h1>Step 3 · Prepare — your packet, your control</h1>
      <p className="lede">
        Review what's missing or expired, preview exactly what the packet contains, then download it
        yourself. RealDoor never sends anything to a property or provider — and you can erase everything
        with one button.
      </p>

      {error && (
        <p role="alert" className="banner alert">
          {error} {error.toLowerCase().includes("confirm") && <Link to="/profile">Go to Step 1 · Profile</Link>}
        </p>
      )}

      {readiness && (
        <>
          <section aria-labelledby="readiness-heading" className="panel">
            <h2 id="readiness-heading" style={{ marginTop: 0 }}>
              Readiness for human review
            </h2>
            <p role="status">
              {readiness.readiness_status === "READY_TO_REVIEW" ? (
                <span className="chip ok">✓ READY_TO_REVIEW</span>
              ) : (
                <span className="chip warn">⚠ NEEDS_REVIEW</span>
              )}{" "}
              — a document-readiness signal for a qualified human reviewer, never an eligibility decision.
            </p>
            <h3>Reasons a human should look closely</h3>
            {readiness.reasons.length === 0 ? (
              <p>None — every readiness check passed.</p>
            ) : (
              <ul className="reason-list">
                {readiness.reasons.map((r) => (
                  <li key={r.code}>
                    <strong>{r.code.replaceAll("_", " ")}</strong> — {r.detail}{" "}
                    <span className="chip neutral">rule {r.rule_id}</span>
                  </li>
                ))}
              </ul>
            )}
            <h3>Checklist gaps (informational)</h3>
            {readiness.checklist_gaps.length === 0 ? (
              <p>No gaps against the checklist.</p>
            ) : (
              <ul>
                {readiness.checklist_gaps.map((g) => (
                  <li key={g.document_type + g.status}>
                    <strong>{g.document_type.replaceAll("_", " ")}</strong> ({g.status}): {g.guidance}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="export-heading" className="panel">
            <h2 id="export-heading" style={{ marginTop: 0 }}>
              Preview and export
            </h2>
            <p>
              The ZIP contains: <code>submission.json</code> (schema-conformant summary),{" "}
              <code>packet_summary.html</code> (printable, human-readable), <code>packet_preview.json</code>{" "}
              (everything shown here), <code>audit_log.json</code>, and copies of your uploaded documents.
              Rule corpus version: <code>{packet?.rule_corpus_version}</code>.
            </p>
            <p>
              <a className="button" href={api.packetExportUrl(sessionId)} download>
                Download my packet (ZIP)
              </a>{" "}
              <Link className="button secondary" to="/profile">
                Edit values first
              </Link>
            </p>
            <details>
              <summary>Show full packet preview (JSON)</summary>
              <pre style={{ overflowX: "auto", background: "#fff", padding: "0.8rem", border: "1px solid var(--line)" }}>
                {JSON.stringify(packet, null, 2)}
              </pre>
            </details>
          </section>
        </>
      )}

      <section aria-labelledby="audit-heading" className="panel">
        <h2 id="audit-heading" style={{ marginTop: 0 }}>
          Audit log (no document contents, ever)
        </h2>
        <p>Every consent, extraction, confirmation, correction, question, export, and deletion is logged with the rule-corpus version — but never your raw values.</p>
        <details>
          <summary>Show {audit.length} audit events</summary>
          <table>
            <caption>Session audit events</caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Event</th>
                <th scope="col">Detail</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((e, i) => (
                <tr key={i}>
                  <td>{new Date(e.ts * 1000).toLocaleTimeString()}</td>
                  <td>{e.event}</td>
                  <td>{e.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>

      <section aria-labelledby="delete-heading" className="panel">
        <h2 id="delete-heading" style={{ marginTop: 0 }}>
          Delete everything
        </h2>
        <p>
          Erases all uploads, extracted values, calculations, and logs from memory immediately. This
          cannot be undone.
        </p>
        {!confirmingDelete ? (
          <button ref={deleteTriggerRef} className="danger" onClick={() => setConfirmingDelete(true)}>
            Delete my session and all data
          </button>
        ) : (
          <div
            role="alertdialog"
            aria-labelledby="del-title"
            aria-describedby="del-desc"
            className="banner alert"
            onKeyDown={(e) => {
              if (e.key === "Escape") cancelDelete();
            }}
          >
            <p id="del-title" style={{ marginTop: 0 }}>
              <strong>Delete everything?</strong>
            </p>
            <p id="del-desc">All session data will be erased from memory. Download your packet first if you want to keep it.</p>
            <button ref={confirmDeleteRef} className="danger" onClick={onDelete}>
              Yes, delete everything
            </button>{" "}
            <button className="secondary" onClick={cancelDelete}>
              Cancel
            </button>
          </div>
        )}
      </section>
    </>
  );
}
