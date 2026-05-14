import type { SubmitProgress } from "../../../wizard/submit";
import { useWizard } from "../../../wizard/store";

export function ReviewStep({ progress }: { progress: SubmitProgress | null }) {
  const s = useWizard();
  const counts = [
    { label: "Plan", n: 1, detail: s.plan.name || "(unnamed)" },
    { label: "People", n: s.people.length },
    { label: "Income sources", n: s.incomes.length },
    { label: "Assets", n: s.assets.length },
    { label: "Properties", n: s.properties.length },
    { label: "Liabilities", n: s.liabilities.length },
    { label: "Goals", n: s.goals.length },
  ];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Review</h3>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {counts.map((c) => (
            <li key={c.label}>
              <strong>{c.label}:</strong> {c.n}
              {c.detail ? ` — ${c.detail}` : ""}
            </li>
          ))}
        </ul>
      </div>

      {progress && (
        <div className="card">
          <h4 style={{ marginTop: 0 }}>Submitting…</h4>
          <div className="muted" style={{ fontSize: 13, color: "#475569" }}>
            Phase: {progress.phase} · {progress.completed}/{progress.total}
          </div>
          <div
            aria-hidden="true"
            style={{
              marginTop: 8,
              height: 6,
              background: "#e2e8f0",
              borderRadius: 3,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.min(100, (progress.completed / Math.max(1, progress.total)) * 100)}%`,
                height: "100%",
                background: "#2563eb",
                transition: "width 200ms ease-out",
              }}
            />
          </div>
          {progress.errors.length > 0 && (
            <ul style={{ marginTop: 12, color: "#991b1b", fontSize: 13 }}>
              {progress.errors.map((e, idx) => (
                <li key={idx}>
                  [{e.phase}] {e.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
