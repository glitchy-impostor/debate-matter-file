// Tracks which card IDs are saved to the matter file. Hydrated once per page
// load via /matter-file/check; mutations update the local set optimistically
// so toggling buttons don't flicker between calls.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as api from "./api.js";

const MatterContext = createContext(null);

export function MatterProvider({ children }) {
  const [savedIds, setSavedIds] = useState(() => new Set());
  const [busy, setBusy] = useState(new Set());
  const [error, setError] = useState(null);

  const hydrate = useCallback(async (ids) => {
    if (!api.enabled()) return;
    try {
      const set = await api.checkSaved(ids);
      setSavedIds((prev) => {
        const next = new Set(prev);
        for (const id of ids) {
          if (set.has(id)) next.add(id);
          else next.delete(id);
        }
        return next;
      });
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const toggle = useCallback(async (card) => {
    if (!api.enabled() || !card?.id) return;
    const id = card.id;
    setBusy((b) => new Set(b).add(id));
    try {
      if (savedIds.has(id)) {
        await api.removeEntry(id);
        setSavedIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      } else {
        await api.addEntry(card);
        setSavedIds((prev) => new Set(prev).add(id));
      }
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setBusy((b) => {
        const next = new Set(b);
        next.delete(id);
        return next;
      });
    }
  }, [savedIds]);

  const value = useMemo(() => ({
    enabled: api.enabled(),
    savedIds,
    busy,
    error,
    clearError: () => setError(null),
    hydrate,
    toggle,
  }), [savedIds, busy, error, hydrate, toggle]);

  return <MatterContext.Provider value={value}>{children}</MatterContext.Provider>;
}

export function useMatter() {
  const ctx = useContext(MatterContext);
  if (!ctx) throw new Error("useMatter must be used inside <MatterProvider>");
  return ctx;
}

// Convenience: hydrate saved-state for a list of cards on mount.
export function useHydrateSaved(cards) {
  const { hydrate } = useMatter();
  useEffect(() => {
    const ids = (cards || []).map((c) => c.id).filter(Boolean);
    if (ids.length) hydrate(ids);
  }, [cards, hydrate]);
}
