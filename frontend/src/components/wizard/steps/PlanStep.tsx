import type { FilingStatus } from "../../../api/types";
import { useWizard } from "../../../wizard/store";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const FILING_OPTIONS: { value: FilingStatus; label: string; description: string }[] = [
  { value: "single", label: "Single", description: "Assessed individually" },
  { value: "married", label: "Married / civil partnership", description: "Joint assessment" },
  {
    value: "cohabiting",
    label: "Cohabiting",
    description: "Living together, not married — taxed individually under Irish law",
  },
];

export function PlanStep() {
  const plan = useWizard((s) => s.plan);
  const setPlan = useWizard((s) => s.setPlan);

  return (
    <div className="card" style={{ display: "grid", gap: 12 }}>
      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Plan name</span>
        <input
          autoFocus
          placeholder="Smith household"
          value={plan.name}
          onChange={(e) => setPlan({ name: e.target.value })}
          style={inputStyle}
        />
      </label>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Base year</span>
          <NumericInput
            integer
            value={plan.base_year ?? NaN}
            onChange={(v) => setPlan({ base_year: Number.isFinite(v) ? v : undefined })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Projection years</span>
          <NumericInput
            integer
            value={plan.projection_years ?? NaN}
            onChange={(v) => setPlan({ projection_years: Number.isFinite(v) ? v : undefined })}
            style={inputStyle}
          />
        </label>
      </div>

      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Filing status</span>
        <ResponsiveSelect<FilingStatus>
          value={(plan.filing_status as FilingStatus | null) ?? "single"}
          onChange={(v) => setPlan({ filing_status: v })}
          options={FILING_OPTIONS}
          label="Filing status"
        />
        <span className="muted" style={{ fontSize: 12, color: "#64748b" }}>
          You can change this later in the editor.
        </span>
      </label>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  fontSize: 16,
  minHeight: 44,
};
