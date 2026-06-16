import { useEffect, useRef, useState, type ReactNode } from "react";

import { useIsMobile } from "../hooks/useIsMobile";

/**
 * Collapses a row's action buttons (Edit / Duplicate / Remove …) into a single
 * "⋯" overflow menu when screen space is limited (mobile). On wider screens the
 * buttons render inline, unchanged.
 *
 * Wraps whatever `renderActions` already returns — the same buttons keep their
 * own handlers, they just move into a popover on mobile — so no per-pane change
 * is needed beyond the table doing the wrapping.
 */
export function RowActions({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!isMobile) return <>{children}</>;

  return (
    <div ref={ref} style={{ position: "relative", marginLeft: "auto" }}>
      <button
        type="button"
        aria-label="Row actions"
        aria-haspopup="menu"
        aria-expanded={open}
        className="btn btn-secondary"
        onClick={() => setOpen((v) => !v)}
        style={{ minHeight: 36, padding: "6px 14px", lineHeight: 1, fontSize: 18 }}
      >
        ⋯
      </button>
      {open && (
        <div
          role="menu"
          className="row-actions-menu"
          // Any click inside (i.e. an action button) dismisses the menu.
          onClick={() => setOpen(false)}
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 4px)",
            background: "#fff",
            border: "1px solid #cbd5e1",
            borderRadius: 8,
            boxShadow: "0 6px 18px rgba(0,0,0,0.14)",
            padding: 6,
            display: "flex",
            flexDirection: "column",
            gap: 6,
            zIndex: 30,
            minWidth: 168,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
