import { useRef, type ReactNode } from "react";

import { useFocusTrap } from "../lib/focusTrap";

export function EditModal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  useFocusTrap({ open, panelRef, onClose });

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.45)",
        zIndex: 1000,
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        padding: "0 8px",
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        style={{
          background: "white",
          width: "100%",
          maxWidth: 560,
          maxHeight: "calc(100vh - 24px)",
          overflowY: "auto",
          borderTopLeftRadius: 12,
          borderTopRightRadius: 12,
          borderBottomLeftRadius: 0,
          borderBottomRightRadius: 0,
          padding: 16,
          boxShadow: "0 -10px 30px rgba(0,0,0,0.15)",
          margin: "auto 0 0 0",
        }}
      >
        <div
          className="row"
          style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}
        >
          <h3 style={{ margin: 0, fontSize: 16 }}>{title ?? "Edit"}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "transparent",
              border: 0,
              fontSize: 22,
              lineHeight: 1,
              padding: "4px 8px",
              cursor: "pointer",
              color: "#64748b",
            }}
          >
            ×
          </button>
        </div>
        {children}
        {footer && <div style={{ marginTop: 16 }}>{footer}</div>}
      </div>
    </div>
  );
}
