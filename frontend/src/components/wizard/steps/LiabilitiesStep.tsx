import type { LiabilityKind } from "../../../api/types";
import { useWizard, type LiabilityDraft } from "../../../wizard/store";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const KINDS: { value: LiabilityKind; label: string; description?: string }[] = [
  { value: "mortgage", label: "Mortgage" },
  { value: "loan", label: "Loan", description: "Personal/car/student" },
];

export function LiabilitiesStep() {
  const liabilities = useWizard((s) => s.liabilities);
  const properties = useWizard((s) => s.properties);
  const addLiability = useWizard((s) => s.addLiability);
  const updateLiability = useWizard((s) => s.updateLiability);
  const removeLiability = useWizard((s) => s.removeLiability);
  const plan = useWizard((s) => s.plan);
  const baseYear = plan.base_year ?? new Date().getFullYear();

  const onAdd = () =>
    addLiability({
      name: "",
      kind: "loan",
      principal: 0,
      interest_rate: 0.05,
      term_months: 60,
      start_year: baseYear,
      monthly_payment: null,
      monthly_overpayment: 0,
      linkedPropertyDraftId: null,
    });

  const propertyOptions: { value: string; label: string }[] = [
    { value: "", label: "(no linked property)" },
    ...properties.map((p) => ({ value: p.draftId, label: p.name || "Unnamed property" })),
  ];

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {liabilities.length === 0 && (
        <div className="muted" style={{ color: "#64748b" }}>
          Add mortgages or other loans.
        </div>
      )}
      {liabilities.map((l) => (
        <LiabilityRow
          key={l.draftId}
          liability={l}
          propertyOptions={propertyOptions}
          onChange={(patch) => updateLiability(l.draftId, patch)}
          onRemove={() => removeLiability(l.draftId)}
        />
      ))}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onAdd}
        style={{ minHeight: 44 }}
      >
        + Add liability
      </button>
    </div>
  );
}

function LiabilityRow({
  liability,
  propertyOptions,
  onChange,
  onRemove,
}: {
  liability: LiabilityDraft;
  propertyOptions: { value: string; label: string }[];
  onChange: (patch: Partial<LiabilityDraft>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={liability.name}
            onChange={(e) => onChange({ name: e.target.value })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Kind</span>
          <ResponsiveSelect<LiabilityKind>
            value={liability.kind}
            onChange={(v) => onChange({ kind: v })}
            options={KINDS}
            label="Liability kind"
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Principal (€)</span>
          <NumericInput
            value={liability.principal}
            onChange={(v) => onChange({ principal: Number.isFinite(v) ? v : 0 })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Interest rate (%)</span>
          <NumericInput
            value={Math.round((liability.interest_rate ?? 0) * 100 * 100) / 100}
            onChange={(v) =>
              onChange({ interest_rate: Number.isFinite(v) ? v / 100 : 0 })
            }
            style={inputStyle}
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Term (months)</span>
          <NumericInput
            integer
            value={liability.term_months}
            onChange={(v) =>
              onChange({ term_months: Number.isFinite(v) ? v : liability.term_months })
            }
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Start year</span>
          <NumericInput
            integer
            value={liability.start_year}
            onChange={(v) =>
              onChange({ start_year: Number.isFinite(v) ? v : liability.start_year })
            }
            style={inputStyle}
          />
        </label>
      </div>
      {liability.kind === "mortgage" && propertyOptions.length > 1 && (
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Linked property</span>
          <ResponsiveSelect<string>
            value={liability.linkedPropertyDraftId ?? ""}
            onChange={(v) => onChange({ linkedPropertyDraftId: v === "" ? null : v })}
            options={propertyOptions}
            label="Linked property"
          />
        </label>
      )}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onRemove}
        style={{ minHeight: 44, alignSelf: "flex-start" }}
      >
        Remove
      </button>
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
