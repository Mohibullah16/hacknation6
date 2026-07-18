import { useEffect, useRef } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useSession } from "./context";
import Landing from "./pages/Landing";
import Profile from "./pages/Profile";
import Understand from "./pages/Understand";
import Prepare from "./pages/Prepare";
import Discover from "./pages/Discover";

const STEPS = [
  { path: "/profile", label: "1 · Profile" },
  { path: "/understand", label: "2 · Understand" },
  { path: "/prepare", label: "3 · Prepare" },
  { path: "/discover", label: "Discover (optional)" },
];

export default function App() {
  const { sessionId } = useSession();
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  /* Move focus to main on route change so keyboard/SR users land on the new
     page content (focus management, WCAG 2.4.3). */
  useEffect(() => {
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="app-header">
        <span className="brand">RealDoor</span>
        <span className="tagline">
          Application-readiness copilot — the AI prepares, you confirm, a qualified human decides.
        </span>
      </header>
      {sessionId && (
        <nav className="stepper" aria-label="Application readiness steps">
          <ol>
            {STEPS.map((s) => (
              <li key={s.path}>
                <NavLink to={s.path} aria-current={location.pathname === s.path ? "page" : undefined}>
                  {s.label}
                </NavLink>
              </li>
            ))}
          </ol>
        </nav>
      )}
      <main id="main" ref={mainRef} tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/understand" element={<Understand />} />
          <Route path="/prepare" element={<Prepare />} />
          <Route path="/discover" element={<Discover />} />
        </Routes>
      </main>
      <footer className="app-footer">
        Research prototype for the Hack-Nation 6th Global AI Hackathon · Synthetic documents only ·
        Never determines eligibility, approval, denial, priority, or availability · Frozen FY 2026 rule
        corpus (effective 2026-05-01)
      </footer>
    </>
  );
}
