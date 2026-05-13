import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

export type ToastKind = "info" | "success" | "error";

export type Toast = {
  id: number;
  kind: ToastKind;
  message: string;
  action?: { label: string; onClick: () => void };
  autoDismissMs?: number;
};

type ToastContextValue = {
  push: (t: Omit<Toast, "id"> & { id?: number }) => number;
  dismiss: (id: number) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    const t = timers.current.get(id);
    if (t) {
      clearTimeout(t);
      timers.current.delete(id);
    }
    setToasts((arr) => arr.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (t: Omit<Toast, "id"> & { id?: number }): number => {
      const id = t.id ?? nextId++;
      const ms = t.autoDismissMs ?? (t.kind === "error" ? 6000 : 4000);
      setToasts((arr) => [...arr, { ...t, id }]);
      if (ms > 0) {
        const timer = setTimeout(() => dismiss(id), ms);
        timers.current.set(id, timer);
      }
      return id;
    },
    [dismiss],
  );

  useEffect(() => {
    const map = timers.current;
    return () => {
      for (const t of map.values()) clearTimeout(t);
      map.clear();
    };
  }, []);

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  useEffect(() => registerToastBridge(push), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        style={{
          position: "fixed",
          bottom: "calc(16px + env(safe-area-inset-bottom))",
          right: 16,
          left: 16,
          display: "flex",
          flexDirection: "column-reverse",
          alignItems: "flex-end",
          gap: 8,
          zIndex: 9999,
          maxWidth: "calc(100vw - 32px)",
          pointerEvents: "none",
        }}
        aria-live="polite"
      >
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const palette = {
    info: { bg: "#1e293b", fg: "#f8fafc", accent: "#60a5fa" },
    success: { bg: "#064e3b", fg: "#ecfdf5", accent: "#34d399" },
    error: { bg: "#7f1d1d", fg: "#fef2f2", accent: "#fca5a5" },
  }[toast.kind];

  return (
    <div
      role="status"
      style={{
        background: palette.bg,
        color: palette.fg,
        borderLeft: `4px solid ${palette.accent}`,
        padding: "10px 14px",
        borderRadius: 6,
        boxShadow: "0 6px 18px rgba(15,23,42,0.18)",
        display: "flex",
        gap: 12,
        alignItems: "center",
        minWidth: 0,
        maxWidth: 420,
        fontSize: 13,
        pointerEvents: "auto",
      }}
    >
      <span style={{ flex: 1 }}>{toast.message}</span>
      {toast.action && (
        <button
          type="button"
          onClick={() => {
            toast.action!.onClick();
            onDismiss();
          }}
          style={{
            background: "transparent",
            color: palette.accent,
            border: `1px solid ${palette.accent}`,
            borderRadius: 4,
            padding: "3px 10px",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: 12,
          }}
        >
          {toast.action.label}
        </button>
      )}
      <button
        type="button"
        aria-label="Dismiss"
        onClick={onDismiss}
        style={{
          background: "transparent",
          color: palette.fg,
          border: "none",
          cursor: "pointer",
          fontSize: 16,
          padding: "0 4px",
        }}
      >
        ×
      </button>
    </div>
  );
}

// Module-level helper for non-component callers (e.g. mutation cache).
// Maintains a stack of registered push functions so concurrent ToastProviders
// (e.g. StrictMode double-mount, route transitions) don't drop toasts when
// one unmounts.
const bridgeStack: Array<ToastContextValue["push"]> = [];

export function registerToastBridge(push: ToastContextValue["push"]): () => void {
  bridgeStack.push(push);
  return () => {
    const i = bridgeStack.lastIndexOf(push);
    if (i >= 0) bridgeStack.splice(i, 1);
  };
}

export function emitToast(t: Omit<Toast, "id">): number | null {
  const top = bridgeStack[bridgeStack.length - 1];
  return top ? top(t) : null;
}
