// Tiny ephemeral toast — used only for matter-file add/remove feedback so a
// dedicated UI library would be overkill. Auto-dismisses after 2.5s.

import { createContext, useCallback, useContext, useEffect, useState } from "react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const push = useCallback((message, kind = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 2500);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto rounded-sm border px-3 py-2 font-mono text-[12px] shadow-wire ${
              t.kind === "error"
                ? "border-red-500/40 bg-red-950/80 text-red-100"
                : t.kind === "success"
                ? "border-wire-econ/40 bg-ink-900/95 text-ink-50"
                : "border-ink-700 bg-ink-900/95 text-ink-100"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

// Optional helper — clears matter-context errors as toasts so callers don't
// need to wire up both contexts manually.
export function useErrorToasts(errorSource) {
  const { push } = useToast();
  const { error, clearError } = errorSource || {};
  useEffect(() => {
    if (error) {
      push(error, "error");
      clearError?.();
    }
  }, [error, clearError, push]);
}
