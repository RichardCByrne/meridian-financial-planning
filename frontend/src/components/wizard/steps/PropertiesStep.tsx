import type { AssetKind } from "../../../api/types";
import { useWizard, type DraftId } from "../../../wizard/store";
import { AssetRow } from "./AssetsStep";

const PROPERTY_KINDS: { value: AssetKind; label: string; description?: string }[] = [
  { value: "property_primary", label: "Primary residence", description: "Principal private residence" },
  { value: "property_btl", label: "Buy-to-let", description: "Investment property" },
];

export function PropertiesStep() {
  const people = useWizard((s) => s.people);
  const properties = useWizard((s) => s.properties);
  const liabilities = useWizard((s) => s.liabilities);
  const addProperty = useWizard((s) => s.addProperty);
  const updateProperty = useWizard((s) => s.updateProperty);
  const removeProperty = useWizard((s) => s.removeProperty);
  const addLiability = useWizard((s) => s.addLiability);
  const updateLiability = useWizard((s) => s.updateLiability);
  const removeLiability = useWizard((s) => s.removeLiability);
  const plan = useWizard((s) => s.plan);
  const baseYear = plan.base_year ?? new Date().getFullYear();

  const onAdd = () =>
    addProperty({
      name: "",
      kind: "property_primary",
      value: 0,
      growth_rate: 0.03,
      cost_basis: 0,
      acquired_year: baseYear,
      ownerPersonDraftId: people[0]?.draftId ?? null,
    });

  const linkedFor = (propertyDraftId: DraftId) =>
    liabilities.find((l) => l.linkedPropertyDraftId === propertyDraftId);

  const onToggleMortgage = (propertyDraftId: DraftId, name: string) => {
    const existing = linkedFor(propertyDraftId);
    if (existing) {
      removeLiability(existing.draftId);
      return;
    }
    addLiability({
      name: `Mortgage – ${name || "property"}`,
      kind: "mortgage",
      principal: 0,
      interest_rate: 0.04,
      term_months: 300,
      start_year: baseYear,
      monthly_payment: null,
      monthly_overpayment: 0,
      linkedPropertyDraftId: propertyDraftId,
    });
  };

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {properties.length === 0 && (
        <div className="muted" style={{ color: "#64748b" }}>
          Add primary residence or buy-to-let properties. You can link a mortgage to each.
        </div>
      )}
      {properties.map((p) => {
        const linked = linkedFor(p.draftId);
        return (
          <AssetRow
            key={p.draftId}
            asset={p}
            people={people.map((x) => ({ draftId: x.draftId, name: x.name }))}
            kindOptions={PROPERTY_KINDS}
            onChange={(patch) => {
              updateProperty(p.draftId, patch);
              if (linked && patch.name) {
                updateLiability(linked.draftId, { name: `Mortgage – ${patch.name}` });
              }
            }}
            onRemove={() => removeProperty(p.draftId)}
            extra={
              <div style={{ display: "grid", gap: 8 }}>
                <label style={{ display: "grid", gap: 4 }}>
                  <span style={{ fontWeight: 600 }}>Cost basis (€)</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    value={p.cost_basis ?? 0}
                    onChange={(e) => updateProperty(p.draftId, { cost_basis: Number(e.target.value) })}
                    style={inputStyle}
                  />
                </label>
                <label style={{ display: "grid", gap: 4 }}>
                  <span style={{ fontWeight: 600 }}>Acquired year</span>
                  <input
                    type="number"
                    inputMode="numeric"
                    value={p.acquired_year ?? baseYear}
                    onChange={(e) =>
                      updateProperty(p.draftId, { acquired_year: Number(e.target.value) })
                    }
                    style={inputStyle}
                  />
                </label>
                <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={!!linked}
                    onChange={() => onToggleMortgage(p.draftId, p.name)}
                  />
                  <span>This property has a mortgage {linked && "✓"}</span>
                </label>
              </div>
            }
          />
        );
      })}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onAdd}
        style={{ minHeight: 44 }}
      >
        + Add property
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
