import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DocumentExtraction, type FieldValue } from "../api";
import EvidenceViewer from "../components/EvidenceViewer";
import { useSession } from "../context";

function confidenceChip(f: FieldValue) {
  if (f.status === "corrected") return <span className="chip ok">✓ corrected by you</span>;
  if (f.status === "confirmed") return <span className="chip ok">✓ confirmed</span>;
  if (f.status === "abstained") return <span className="chip alert">✋ abstained — needs your entry</span>;
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
      const income = r.calc ? ` Annualized income is now $${r.calc.annualized_income.toLocaleString(undefined, { minimumFractionDigits: 2 })}.` : "";
      announce(`${field} ${action === "confirm" ? "confirmed" : "corrected"}.${income}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Update failed.";
      setError(msg);
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
      {busy && <p aria-hidden="true">Working…</p>}

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
                              className="secondary"
                              style={{ minHeight: 32, padding: "0.2rem 0.6rem" }}
                              onClick={() => setFocusField(focusField === f.field ? null : f.field)}
                              aria-pressed={focusField === f.field}
                              aria-label={`Highlight source box for ${f.field} on the document preview`}
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
                                  autoFocus
                                />
                                <button type="submit" style={{ marginTop: "0.3rem" }}>
                                  Save
                                </button>{" "}
                                <button type="button" className="secondary" style={{ marginTop: "0.3rem" }} onClick={() => setEditing(null)}>
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
                              className="secondary"
                              disabled={f.status === "confirmed" || f.status === "corrected" || f.value === null || busy}
                              onClick={() => act(active.document_id, f.field, "confirm")}
                            >
                              Confirm
                            </button>{" "}
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => {
                                setEditing(f.field);
                                setEditValue(f.value === null ? "" : String(f.value));
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

          <div className={remaining === 0 ? "banner" : "banner warn"} role="status">
            {remaining === 0 ? (
              <>
                <strong>✓ Profile confirmed.</strong> Every value is confirmed or corrected — continue to{" "}
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
