import type { ChildDraft } from "../../../wizard/store";
import { useWizard } from "../../../wizard/store";
import { HelpTip } from "../../HelpTip";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

export function ChildrenStep() {
  const children = useWizard((s) => s.children);
  const people = useWizard((s) => s.people);
  const addChild = useWizard((s) => s.addChild);
  const updateChild = useWizard((s) => s.updateChild);
  const removeChild = useWizard((s) => s.removeChild);

  const carerOptions: { value: string; label: string }[] = [
    { value: "", label: "(plan's primary person)" },
    ...people.map((p) => ({ value: p.draftId, label: p.name || "Unnamed" })),
  ];

  const onAdd = () =>
    addChild({
      name: "",
      dob: `${new Date().getFullYear()}-01-01`,
      primaryCarerDraftId: null,
      childcare_annual: 0,
      primary_annual: 0,
      secondary_annual: 0,
      secondary_is_private: false,
      secondary_private_fee_annual: 0,
      everyday_annual: 0,
    });

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="muted" style={{ color: "#64748b" }}>
        Optional. Children drive Child Benefit (€140/mo until 18) and age-gated rearing costs
        (childcare, school, optional private fees, everyday spend). Skip if not relevant — you can
        always add them later.
      </div>
      {children.map((c) => (
        <ChildRow
          key={c.draftId}
          child={c}
          carerOptions={carerOptions}
          onChange={(patch) => updateChild(c.draftId, patch)}
          onRemove={() => removeChild(c.draftId)}
        />
      ))}
      <button type="button" className="btn btn-secondary" onClick={onAdd} style={{ minHeight: 44 }}>
        + Add child
      </button>
    </div>
  );
}

function ChildRow({
  child,
  carerOptions,
  onChange,
  onRemove,
}: {
  child: ChildDraft;
  carerOptions: { value: string; label: string }[];
  onChange: (patch: Partial<ChildDraft>) => void;
  onRemove: () => void;
}) {
  const num = (v: number) => (Number.isFinite(v) ? Math.max(0, v) : 0);
  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={child.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="e.g. Saoirse"
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Date of birth</span>
          <input
            type="date"
            value={child.dob}
            onChange={(e) => onChange({ dob: e.target.value })}
            style={inputStyle}
          />
        </label>
      </div>

      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Primary carer (receives Child Benefit)</span>
        <ResponsiveSelect<string>
          value={child.primaryCarerDraftId ?? ""}
          onChange={(v) => onChange({ primaryCarerDraftId: v === "" ? null : v })}
          options={carerOptions}
          label="Primary carer"
        />
      </label>

      <div style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
        Rearing costs (€ / year)
        <HelpTip>
          Each applies automatically over the matching life stage by the child's age and escalates
          with inflation. Leave any at 0 to skip it. Leave everyday at 0 if food/clothes are already
          in your household Expenses (to avoid double-counting). College is modelled via a goal.
        </HelpTip>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <CostField label="Childcare (0–4)" value={child.childcare_annual ?? 0}
          onChange={(v) => onChange({ childcare_annual: num(v) })} />
        <CostField label="Primary (5–12)" value={child.primary_annual ?? 0}
          onChange={(v) => onChange({ primary_annual: num(v) })} />
        <CostField label="Secondary (13–17)" value={child.secondary_annual ?? 0}
          onChange={(v) => onChange({ secondary_annual: num(v) })} />
        <CostField label="Everyday food/clothes" value={child.everyday_annual ?? 0}
          onChange={(v) => onChange({ everyday_annual: num(v) })} />
      </div>
      <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <input
          type="checkbox"
          checked={child.secondary_is_private ?? false}
          onChange={(e) => onChange({ secondary_is_private: e.target.checked })}
        />
        Private secondary school
      </label>
      {child.secondary_is_private && (
        <CostField label="Private secondary fees" value={child.secondary_private_fee_annual ?? 0}
          onChange={(v) => onChange({ secondary_private_fee_annual: num(v) })} />
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

function CostField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <label style={{ display: "grid", gap: 4 }}>
      <span style={{ fontWeight: 600 }}>{label}</span>
      <NumericInput value={value} onChange={onChange} style={inputStyle} />
    </label>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "10px 12px",
  border: "1px solid #cbd5e1",
  borderRadius: 6,
  fontSize: 16,
  minHeight: 44,
};
