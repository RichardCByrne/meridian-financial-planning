import type { ReactNode } from "react";

// Shared empty-state hint for panes. Sits where "No X yet." used to.
// `hint` is the value-prop / next-action copy; `children` is an optional
// CTA button when a primary action belongs outside the existing form.
//
// Most panes already render an "Add" form above the list, so the default
// usage is just the title + hint; no extra button required.
export function EmptyState({
  title,
  hint,
  children,
}: {
  title: string;
  hint: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div
      style={{
        padding: "18px 16px",
        textAlign: "center",
        background: "#f8fafc",
        border: "1px dashed #cbd5e1",
        borderRadius: 8,
      }}
    >
      <div style={{ fontWeight: 600, color: "#334155", marginBottom: 4 }}>{title}</div>
      <div style={{ color: "#64748b", fontSize: 13, maxWidth: 460, margin: "0 auto" }}>{hint}</div>
      {children && <div style={{ marginTop: 10 }}>{children}</div>}
    </div>
  );
}
