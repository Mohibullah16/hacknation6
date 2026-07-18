import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CalcResult, type QAAnswer, type ReadinessResult } from "../api";
import { useSession } from "../context";

const SUGGESTED = [
  "What is the frozen 60% threshold for my household?",
  "What annualized income does the calculation use?",
  "How does my amount compare with the frozen threshold?",
  "Is the 60-day currency rule an official universal LIHTC rule?",
  "Am I eligible?",
];

export default function Understand() {
  const { sessionId, session, announce } = useSession();
  const [calc, setCalc] = useState<CalcResult | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResult | null>(null);
  const [blocked, setBlocked] = useState<string>("");
  const [question, setQuestion] = useState("");
  const [qa, setQa] = useState<QAAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    api
      .getCalculation(sessionId)
      .then((r) => {
        if (r.status === "ok" && r.calc && r.readiness) {
          setCalc(r.calc);
          setReadiness(r.readiness);
          setBlocked("");
        } else {
          setBlocked(r.message ?? "Confirm your profile first.");
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the calculation."));
  }, [sessionId, session]);

  async function ask(q: string) {
    if (!sessionId || !q.trim()) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.askQuestion(sessionId, q);
      setQa(r);
      announce(r.abstained ? "The copilot abstained from answering." : "Answer received, with citation.");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Question failed.";
      setError(msg);
      announce(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  if (!sessionId) {
    return (
      <>
        <h1>Step 2 · Understand</h1>
        <p>
          No active session. Please <Link to="/">start a session</Link> first.
        </p>
      </>
    );
  }

  return (
    <>
      <h1>Step 2 · Understand — cited rules and deterministic math</h1>
      <p className="lede">
        Everything below is computed by transparent arithmetic over your confirmed values and the frozen
        FY 2026 rule corpus — no model guesses a number, and nothing here is an eligibility decision.
      </p>

      {blocked && (
        <p className="banner warn" role="status">
          {blocked} Go back to <Link to="/profile">Step 1 · Profile</Link>.
        </p>
      )}
      {error && (
        <p role="alert" className="banner alert">
          {error}
        </p>
      )}

      {calc && (
        <section aria-labelledby="calc-heading" className="panel">
          <h2 id="calc-heading" style={{ marginTop: 0 }}>
            Deterministic calculation
          </h2>
          <table>
            <caption>Income sources (each cited to its source box)</caption>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Document</th>
                <th scope="col">Formula</th>
                <th scope="col">Annualized</th>
              </tr>
            </thead>
            <tbody>
              {calc.sources.map((s) => (
                <tr key={s.document_id + s.source_type}>
                  <th scope="row">{s.source_type}</th>
                  <td>{s.document_id}</td>
                  <td>{s.formula}</td>
                  <td>${s.annualized.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            <strong>Total annualized documented recurring gross income:</strong>{" "}
            ${calc.annualized_income.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
          <p>
            <strong>Frozen 60% MTSP threshold</strong> (household size {calc.household_size}):{" "}
            {calc.threshold !== null ? `$${calc.threshold.toLocaleString()}` : "no frozen threshold"} ·
            rule <code>{calc.threshold_rule_id}</code> · effective {calc.threshold_effective_date} ·{" "}
            <a href={calc.threshold_source_url ?? "#"} target="_blank" rel="noreferrer">
              official HUD source (opens in new tab)
            </a>
          </p>
          <p>
            <strong>Comparison:</strong>{" "}
            <span className={calc.comparison === "above" ? "chip warn" : "chip neutral"}>
              {calc.comparison === "below_or_equal" && "≤ at or below the frozen threshold"}
              {calc.comparison === "above" && "▲ above the frozen threshold"}
              {calc.comparison === "no_frozen_threshold" && "✋ no frozen threshold for this size"}
            </span>{" "}
            — a numerical comparison only. Only the housing program's human reviewer can determine what it
            means for your application.
          </p>
          {readiness && (
            <p role="status">
              Readiness signal:{" "}
              {readiness.readiness_status === "READY_TO_REVIEW" ? (
                <span className="chip ok">✓ READY_TO_REVIEW — packet looks complete for human review</span>
              ) : (
                <span className="chip warn">⚠ NEEDS_REVIEW — see reasons in Step 3</span>
              )}
            </p>
          )}
        </section>
      )}

      <section aria-labelledby="qa-heading">
        <h2 id="qa-heading">Ask about the rules</h2>
        <p>
          Answers come only from the frozen, versioned corpus and always carry a citation. When the corpus
          doesn't cover a question, the copilot says so instead of guessing.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
        >
          <label htmlFor="qa-input">Your question</label>
          <input
            id="qa-input"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the frozen 60% threshold for my household?"
          />
          <button type="submit" disabled={busy || !question.trim()} style={{ marginLeft: "0.5rem" }}>
            Ask
          </button>
        </form>
        <p>
          {SUGGESTED.map((s) => (
            <button
              key={s}
              className="secondary"
              style={{ margin: "0.25rem 0.4rem 0 0" }}
              onClick={() => {
                setQuestion(s);
                ask(s);
              }}
              disabled={busy}
            >
              {s}
            </button>
          ))}
        </p>
        {qa && (
          <div className="qa-answer" role="region" aria-label="Answer with citations">
            <p style={{ marginTop: 0 }}>{qa.answer}</p>
            {qa.authority_label && (
              <p>
                <span className={qa.authority_label.startsWith("Official") ? "chip ok" : "chip warn"}>
                  {qa.authority_label}
                </span>
              </p>
            )}
            {qa.citations.map((c) => (
              <p className="citation" key={c.rule_id}>
                <strong>{c.rule_id}</strong> ({c.authority}
                {c.effective_date ? `, effective ${c.effective_date}` : ""}) — “{c.rule_text}” ·{" "}
                <a href={c.source_url} target="_blank" rel="noreferrer">
                  source: {c.source_locator} (opens in new tab)
                </a>
              </p>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
