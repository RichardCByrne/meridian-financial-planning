import { useEffect, useState } from "react";

import { EditModal } from "./EditModal";

type ConfirmRequest = {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
};

type PromptRequest = {
  title?: string;
  message?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
};

type Pending =
  | { kind: "confirm"; req: ConfirmRequest; resolve: (v: boolean) => void }
  | { kind: "prompt"; req: PromptRequest; resolve: (v: string | null) => void };

// Single-host pattern: one ConfirmDialogHost is mounted at the app root and
// receives requests via this module-level queue. Mirrors emitToast in Toast.tsx.
let pushPending: ((p: Pending) => void) | null = null;

export function confirmDialog(req: ConfirmRequest): Promise<boolean> {
  return new Promise((resolve) => {
    if (!pushPending) {
      // Fallback if the host isn't mounted (tests / SSR). Default to declining
      // the destructive action so we never auto-confirm a delete.
      resolve(false);
      return;
    }
    pushPending({ kind: "confirm", req, resolve });
  });
}

export function promptDialog(req: PromptRequest): Promise<string | null> {
  return new Promise((resolve) => {
    if (!pushPending) {
      resolve(null);
      return;
    }
    pushPending({ kind: "prompt", req, resolve });
  });
}

export function ConfirmDialogHost() {
  const [current, setCurrent] = useState<Pending | null>(null);
  const [promptValue, setPromptValue] = useState("");

  useEffect(() => {
    pushPending = (p) => {
      if (p.kind === "prompt") setPromptValue(p.req.defaultValue ?? "");
      setCurrent(p);
    };
    return () => {
      pushPending = null;
    };
  }, []);

  if (!current) return null;

  const settle = (value: boolean | string | null) => {
    if (current.kind === "confirm") {
      current.resolve(value as boolean);
    } else {
      current.resolve(value as string | null);
    }
    setCurrent(null);
  };

  const onCancel = () => settle(current.kind === "confirm" ? false : null);

  if (current.kind === "confirm") {
    const { title, message, confirmLabel, cancelLabel, danger } = current.req;
    return (
      <EditModal open onClose={onCancel} title={title ?? "Confirm"}>
        <p style={{ margin: "0 0 12px 0", color: "#334155", fontSize: 14 }}>{message}</p>
        <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {cancelLabel ?? "Cancel"}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => settle(true)}
            autoFocus
            style={
              danger
                ? { background: "#dc2626", borderColor: "#dc2626", color: "white" }
                : undefined
            }
          >
            {confirmLabel ?? "Confirm"}
          </button>
        </div>
      </EditModal>
    );
  }

  // prompt
  const { title, message, placeholder, confirmLabel, cancelLabel } = current.req;
  return (
    <EditModal open onClose={onCancel} title={title ?? "Enter a value"}>
      {message && (
        <p style={{ margin: "0 0 8px 0", color: "#334155", fontSize: 14 }}>{message}</p>
      )}
      <div className="field" style={{ marginBottom: 12 }}>
        <input
          autoFocus
          value={promptValue}
          placeholder={placeholder}
          onChange={(e) => setPromptValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              settle(promptValue);
            }
          }}
          style={{ width: "100%", padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: 6 }}
        />
      </div>
      <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          {cancelLabel ?? "Cancel"}
        </button>
        <button type="button" className="btn" onClick={() => settle(promptValue)}>
          {confirmLabel ?? "OK"}
        </button>
      </div>
    </EditModal>
  );
}
