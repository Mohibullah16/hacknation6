import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSession } from "../context";

const DATA_USES = [
  {
    category: "Identity fields (name, address, household size)",
    purpose: "Match documents to one household and pick the right frozen income threshold.",
  },
  {
    category: "Income fields (pay dates, hours, rates, gross amounts, benefits, gig receipts)",
    purpose: "Deterministically annualize documented recurring gross income and compare it with the frozen 60% MTSP limit.",
  },
  {
    category: "Document dates",
    purpose: "Check the simulation's 60-day document-currency convention.",
  },
];

export default function Landing() {
  const { start, announce } = useSession();
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function begin() {
    setBusy(true);
    setError("");
    try {
      await start();
      navigate("/profile");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not start a session.";
      setError(msg);
      announce(`Error: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Get application-ready — without being judged by a machine</h1>
      <p className="lede">
        RealDoor helps you turn pay stubs and benefit letters into a <strong>you-confirmed</strong>{" "}
        profile, explains one frozen affordable-housing rule set with citations, checks your documents
        for gaps, and builds a packet <strong>you</strong> control. It never decides eligibility — a
        qualified human reviewer at the housing program does that.
      </p>

      <div className="banner">
        <strong>How your data is used — and not used.</strong> Only the allowlisted fields below are ever
        extracted. Documents stay in this session's memory only, are never sent to a property or
        provider, are never used for training, and are erased when you delete the session.
      </div>

      <table>
        <caption>Every data use, explained before you start</caption>
        <thead>
          <tr>
            <th scope="col">What we read</th>
            <th scope="col">Why we read it</th>
          </tr>
        </thead>
        <tbody>
          {DATA_USES.map((d) => (
            <tr key={d.category}>
              <td>{d.category}</td>
              <td>{d.purpose}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="panel">
        <label htmlFor="consent" style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start", fontWeight: 400 }}>
          <input
            id="consent"
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            style={{ width: "1.4rem", height: "1.4rem", minHeight: 0, marginTop: "0.2rem" }}
          />
          <span>
            I consent to extraction of the allowlisted fields above from documents I upload, for the sole
            purpose of preparing my application-readiness packet. I can correct any value and delete
            everything at any time.
          </span>
        </label>
        <p style={{ marginBottom: 0 }}>
          <button onClick={begin} disabled={!consent || busy}>
            {busy ? "Starting…" : "Start my session"}
          </button>
        </p>
        {error && (
          <p role="alert" className="banner alert">
            {error}
          </p>
        )}
      </div>

      <h2>What happens in the three steps</h2>
      <ol>
        <li>
          <strong>Profile</strong> — upload synthetic documents; every extracted value shows its source box
          and confidence, and waits for your confirmation or correction.
        </li>
        <li>
          <strong>Understand</strong> — see the deterministic calculation, the frozen threshold with its
          effective date, and ask rules questions that are always answered with citations.
        </li>
        <li>
          <strong>Prepare</strong> — review gaps, preview and download your packet, and delete the session.
        </li>
      </ol>
    </>
  );
}
