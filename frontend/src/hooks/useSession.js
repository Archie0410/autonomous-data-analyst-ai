import { useEffect, useState } from "react";

const KEY = "aida.session_id";

function generateId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "s_" + Math.random().toString(36).slice(2, 10);
}

export function useSession() {
  const [sessionId, setSessionId] = useState(() => {
    const v = localStorage.getItem(KEY);
    if (v) return v;
    const fresh = generateId();
    localStorage.setItem(KEY, fresh);
    return fresh;
  });

  useEffect(() => {
    localStorage.setItem(KEY, sessionId);
  }, [sessionId]);

  function reset() {
    const fresh = generateId();
    setSessionId(fresh);
  }

  return { sessionId, reset };
}
