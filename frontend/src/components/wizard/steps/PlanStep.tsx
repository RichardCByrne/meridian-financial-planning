import type { FilingStatus } from "../../../api/types";
import { useWizard } from "../../../wizard/store";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const FILING_OPTIONS: { value: FilingStatus | "auto"; label: string; description: string }[] = [
  { value: "auto", label: "Auto-detect", description: "Inferred from household structure" },
  { value: "single", label: "Single", description: "Assessed individually" },
  { value: "married", label: "Married / civil partnership", description: "Joint assessment" },
  { value: "cohabiting", label: "Cohabiting", description: "Treated individually under Irish law" },
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
          <input
            type="number"
            inputMode="numeric"
            value={plan.base_year ?? ""}
            onChange={(e) => setPlan({ base_year: Number(e.target.value) || undefined })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Projection years</span>
          <input
            type="number"
            inputMode="numeric"
            value={plan.projection_years ?? ""}
            onChange={(e) => setPlan({ projection_years: Number(e.target.value) || undefined })}
            style={inputStyle}
          />
        </label>
      </div>

      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Filing status</span>
        <ResponsiveSelect<FilingStatus | "auto">
          value={(plan.filing_status as FilingStatus | null) ?? "auto"}
          onChange={(v) => setPlan({ filing_status: v === "auto" ? null : v })}
          options={FILING_OPTIONS}
          label="Filing status"
        />
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
