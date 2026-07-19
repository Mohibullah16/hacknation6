import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DocumentExtraction, type FieldValue } from "../api";
import EvidenceViewer from "../components/EvidenceViewer";
import { useSession } from "../context";

/* Symbols in chips are decorative (the text carries the meaning) and are
   hidden from screen readers so they aren't spoken as noise ("white heavy
   check mark", "raised hand", …). */
function confidenceChip(f: FieldValue) {
  if (f.status === "corrected")
    return (
      <span className="chip ok">
        <span aria-hidden="true">✓ </span>corrected by you
      </span>
    );
  if (f.status === "confirmed")
    return (
      <span className="chip ok">
        <span aria-hidden="true">✓ </span>confirmed
      </span>
    );
  if (f.status === "abstained")
    return (
      <span className="chip alert">
        <span aria-hidden="true">✋ </span>abstained — needs your entry
      </span>
    );
  if (f.confidence >= 0.9) return <span className="chip neutral">extracted · high confidence ({Math.round(f.confidence * 100)}%)</span>;
  return <span className="chip warn">extracted · check carefully ({Math.round(f.confidence * 100)}%)</span>;
}

export default function Profile() {
  const { sessionId, session, refresh, announce } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [focusField, setFocusField] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null); // field name being corrected
  const [editValue, setEditValue] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  /* Element id to focus after the next render. Confirming/correcting disables
     or unmounts the button that was pressed, which would otherwise drop
     keyboard focus to <body> and force the user to Tab from the top of the
     page again (WCAG 2.4.3). */
  const [pendingFocus, setPendingFocus] = useState<string | null>(null);

  useEffect(() => {
    if (!pendingFocus) return;
    document.getElementById(pendingFocus)?.focus();
    setPendingFocus(null);
  }, [pendingFocus]);

  if (!sessionId || !session) {
    return (
      <>
        <h1>Step 1 · Profile</h1>
        <p>
          No active session. Please <Link to="/">start a session with consent</Link> first.
        </p>
      </>
    );
  }

  const docs = session.documents;
  const active: DocumentExtraction | undefined = docs.find((d) => d.document_id === activeDocId) ?? docs[0];

  async function onUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const doc = await api.uploadDocument(sessionId!, file);
        setActiveDocId(doc.document_id);
        announce(
          `Extracted ${doc.fields.length} fields from ${doc.document_type.replaceAll("_", " ")} ${doc.document_id}.` +
            (doc.adversarial_text_detected ? " Warning: embedded instructions were detected and ignored." : ""),
        );
      }
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed.";
      setError(msg);
      announce(`Error: ${msg}`);
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function act(docId: string, field: string, action: "confirm" | "correct", value?: string) {
    setBusy(true);
    setError("");
    try {
      const r = await api.updateField(sessionId!, docId, field, action, value);
      await refresh();
      setEditing(null);
      if (action === "confirm") {
        // Keep the keyboard on the work: land on the next unconfirmed row's
        // field/zoom button (so the user can inspect the source box before
        // confirming), or the status banner once this document is done.
        const fields = active?.fields ?? [];
        const idx = fields.findIndex((f) => f.field === field);
        const needsAction = (f: FieldValue) =>
          f.field !== field && f.status !== "confirmed" && f.status !== "corrected" && f.value !== null;
        const next = fields.find((f, i) => i > idx && needsAction(f)) ?? fields.find(needsAction);
        setPendingFocus(next ? `field-${next.field}` : "profile-status");
      } else {
        setPendingFocus(`correct-${field}`);
      }
      const income = r.calc ? ` Annualized income is now $${r.calc.annualized_income.toLocaleString(undefined, { minimumFractionDigits: 2 })}.` : "";
      announce(`${field} ${action === "confirm" ? "confirmed" : "corrected"}.${income}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Update failed.";
      setError(msg);
      setPendingFocus(action === "confirm" ? `confirm-${field}` : `correct-${field}`);
      announce(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirmAll(docId: string) {
    setBusy(true);
    setError("");
    try {
      await api.confirmAll(sessionId!, docId);
      await refresh();
      setPendingFocus("profile-status");
      announce(`All extracted values on ${docId} confirmed. Downstream calculation updated.`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not confirm.";
      setError(msg);
      announce(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  const remaining = session.unconfirmed_fields.length;

  return (
    <>
      <h1>Step 1 · Profile — you confirm every value</h1>
      <p className="lede">
        Upload synthetic pay stubs, letters, or statements. Only allowlisted fields are extracted; each
        one shows its exact source box and confidence, and nothing is used downstream until you confirm
        or correct it.
      </p>

      <div className="panel">
        <label htmlFor="file-upload">Upload synthetic PDF document(s)</label>
        <input
          id="file-upload"
          ref={fileInput}
          type="file"
          accept="application/pdf"
          multiple
          onChange={(e) => onUpload(e.target.files)}
          aria-describedby="upload-hint"
        />
        <p id="upload-hint" style={{ color: "var(--muted)", marginBottom: 0 }}>
          PDF only, up to 5 MB each. Documents never leave this session and are never auto-sent anywhere.
        </p>
      </div>

      {error && (
        <p role="alert" className="banner alert">
          {error}
        </p>
      )}
      {/* Perceivable to screen readers browsing the page too; completion is
          announced separately via the polite live region. */}
      {busy && <p>Working…</p>}

      {docs.length > 0 && (
        <>
          <h2 id="doc-list-heading">Your documents ({docs.length})</h2>
          <div role="group" aria-labelledby="doc-list-heading" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {docs.map((d) => (
              <button
                key={d.document_id}
                className={d.document_id === active?.document_id ? "" : "secondary"}
                aria-pressed={d.document_id === active?.document_id}
                onClick={() => {
                  setActiveDocId(d.document_id);
                  setFocusField(null);
                }}
              >
                {d.document_type.replaceAll("_", " ")} · {d.document_id}
              </button>
            ))}
          </div>

          {active && (
            <section aria-label={`Extracted evidence for ${active.document_id}`}>
              {active.adversarial_text_detected && (
                <p className="banner warn" role="note">
                  <strong>Untrusted content ignored:</strong> {active.adversarial_note} Embedded
                  instructions can never change how this tool behaves.
                </p>
              )}
              {(active.advisory_flags?.length ?? 0) > 0 && (
                <div className="banner" role="note">
                  <strong>
                    <span aria-hidden="true">🔍 </span>AI cross-check suggests a second look (advisory only — nothing was changed):
                  </strong>
                  <ul style={{ margin: "0.3rem 0 0" }}>
                    {active.advisory_flags!.map((f) => (
                      <li key={f.field}>
                        <strong>{f.field.replaceAll("_", " ")}</strong>: {f.note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="evidence-layout">
                <div>
                  <table>
                    <caption>
                      Extracted fields — {active.document_id} ({active.rasterized ? "scanned image, OCR" : "digital text"})
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">Field</th>
                        <th scope="col">Value</th>
                        <th scope="col">Status</th>
                        <th scope="col">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {active.fields.map((f) => (
                        <tr key={f.field}>
                          <th scope="row">
                            <button
                              id={`field-${f.field}`}
                              className="secondary"
                              style={{ minHeight: 32, padding: "0.2rem 0.6rem" }}
                              onClick={() => setFocusField(focusField === f.field ? null : f.field)}
                              aria-pressed={focusField === f.field}
                              aria-label={`Highlight and zoom to the source box for ${f.field} on the document preview`}
                            >
                              {f.field.replaceAll("_", " ")}
                            </button>
                          </th>
                          <td>
                            {editing === f.field ? (
                              <form
                                onSubmit={(e) => {
                                  e.preventDefault();
                                  act(active.document_id, f.field, "correct", editValue);
                                }}
                              >
                                <label htmlFor={`edit-${f.field}`} className="visually-hidden">
                                  New value for {f.field}
                                </label>
                                <input
                                  id={`edit-${f.field}`}
                                  type="text"
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                />
                                <button type="submit" style={{ marginTop: "0.3rem" }}>
                                  Save
                                </button>{" "}
                                <button
                                  type="button"
                                  className="secondary"
                                  style={{ marginTop: "0.3rem" }}
                                  onClick={() => {
                                    setEditing(null);
                                    setPendingFocus(`correct-${f.field}`);
                                  }}
                                >
                                  Cancel
                                </button>
                              </form>
                            ) : f.value === null ? (
                              <em>— needs your entry (page {f.page}, box shown)</em>
                            ) : (
                              String(f.value)
                            )}
                          </td>
                          <td>{confidenceChip(f)}</td>
                          <td>
                            <button
                              id={`confirm-${f.field}`}
                              className="secondary"
                              disabled={f.status === "confirmed" || f.status === "corrected" || f.value === null || busy}
                              onClick={() => act(active.document_id, f.field, "confirm")}
                            >
                              Confirm
                            </button>{" "}
                            <button
                              id={`correct-${f.field}`}
                              className="secondary"
                              disabled={busy}
                              onClick={() => {
                                setEditing(f.field);
                                setEditValue(f.value === null ? "" : String(f.value));
                                setFocusField(f.field);
                                setPendingFocus(`edit-${f.field}`);
                              }}
                            >
                              Correct
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button onClick={() => confirmAll(active.document_id)} disabled={busy}>
                    Confirm all extracted values on this document
                  </button>
                </div>
                <EvidenceViewer
                  fileUrl={api.documentFileUrl(sessionId, active.document_id)}
                  documentId={active.document_id}
                  fields={active.fields}
                  focusField={focusField}
                />
              </div>
            </section>
          )}

          <div id="profile-status" tabIndex={-1} className={remaining === 0 ? "banner" : "banner warn"} role="status">
            {remaining === 0 ? (
              <>
                <strong>
                  <span aria-hidden="true">✓ </span>Profile confirmed.
                </strong>{" "}
                Every value is confirmed or corrected — continue to{" "}
                <Link to="/understand">Step 2 · Understand</Link>.
              </>
            ) : (
              <>
                <strong>{remaining} value(s)</strong> still need your confirmation or correction before the
                calculation unlocks. The renter — not the model — owns this profile.
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
