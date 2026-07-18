import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { api, type SessionState } from "./api";

interface Ctx {
  sessionId: string | null;
  session: SessionState | null;
  start: () => Promise<void>;
  refresh: () => Promise<void>;
  clear: () => void;
  announce: (msg: string) => void;
}

const SessionContext = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionState | null>(null);
  const [liveMsg, setLiveMsg] = useState("");
  const liveTimer = useRef<number | undefined>(undefined);

  /* Screen-reader status announcements (WCAG 4.1.3). Clearing first ensures
     repeated identical messages are re-announced. */
  const announce = useCallback((msg: string) => {
    window.clearTimeout(liveTimer.current);
    setLiveMsg("");
    liveTimer.current = window.setTimeout(() => setLiveMsg(msg), 120);
  }, []);

  const start = useCallback(async () => {
    const r = await api.createSession();
    setSessionId(r.session_id);
    setSession(await api.getSession(r.session_id));
    announce("Session started. You can now upload documents.");
  }, [announce]);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    setSession(await api.getSession(sessionId));
  }, [sessionId]);

  const clear = useCallback(() => {
    setSessionId(null);
    setSession(null);
  }, []);

  return (
    <SessionContext.Provider value={{ sessionId, session, start, refresh, clear, announce }}>
      {children}
      <div aria-live="polite" role="status" className="visually-hidden">
        {liveMsg}
      </div>
    </SessionContext.Provider>
  );
}

export function useSession(): Ctx {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside provider");
  return ctx;
}
