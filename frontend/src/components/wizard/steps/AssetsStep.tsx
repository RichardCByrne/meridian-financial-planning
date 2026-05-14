import type { AssetKind } from "../../../api/types";
import { useWizard, type AssetDraft, type DraftId } from "../../../wizard/store";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const NON_PROPERTY_KINDS: { value: AssetKind; label: string; description?: string }[] = [
  { value: "cash", label: "Cash", description: "Current/instant access" },
  { value: "deposit", label: "Deposit", description: "Bank deposit, term account" },
  { value: "investment_unwrapped", label: "Investment (unwrapped)", description: "CGT-bearing" },
  { value: "etf_fund", label: "ETF / fund", description: "8-year deemed disposal" },
  { value: "prsa", label: "PRSA", description: "Personal pension wrapper" },
  { value: "occupational_pension", label: "Occupational pension", description: "Employer scheme" },
  { value: "arf", label: "ARF", description: "Approved Retirement Fund" },
];

export function AssetsStep() {
  const people = useWizard((s) => s.people);
  const assets = useWizard((s) => s.assets);
  const addAsset = useWizard((s) => s.addAsset);
  const updateAsset = useWizard((s) => s.updateAsset);
  const removeAsset = useWizard((s) => s.removeAsset);

  const onAdd = () =>
    addAsset({
      name: "",
      kind: "cash",
      value: 0,
      growth_rate: 0.04,
      ownerPersonDraftId: people[0]?.draftId ?? null,
    });

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {assets.length === 0 && (
        <div className="muted" style={{ color: "#64748b" }}>
          Add cash, deposits, investments, and pensions. Property goes in the next step.
        </div>
      )}
      {assets.map((a) => (
        <AssetRow
          key={a.draftId}
          asset={a}
          people={people.map((p) => ({ draftId: p.draftId, name: p.name }))}
          onChange={(patch) => updateAsset(a.draftId, patch)}
          onRemove={() => removeAsset(a.draftId)}
        />
      ))}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={onAdd}
        style={{ minHeight: 44 }}
      >
        + Add asset
      </button>
    </div>
  );
}

export function AssetRow({
  asset,
  people,
  kindOptions = NON_PROPERTY_KINDS,
  extra,
  onChange,
  onRemove,
}: {
  asset: AssetDraft;
  people: { draftId: DraftId; name: string }[];
  kindOptions?: { value: AssetKind; label: string; description?: string }[];
  extra?: React.ReactNode;
  onChange: (patch: Partial<AssetDraft>) => void;
  onRemove: () => void;
}) {
  const ownerOptions: { value: string; label: string }[] = [
    { value: "", label: "(no owner)" },
    ...people.map((p) => ({ value: p.draftId, label: p.name || "Unnamed" })),
  ];

  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={asset.name}
            onChange={(e) => onChange({ name: e.target.value })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Kind</span>
          <ResponsiveSelect<AssetKind>
            value={asset.kind}
            onChange={(v) => onChange({ kind: v })}
            options={kindOptions}
            label="Asset kind"
          />
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Value (€)</span>
          <input
            type="number"
            inputMode="decimal"
            value={asset.value}
            onChange={(e) => onChange({ value: Number(e.target.value) })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Growth rate (e.g. 0.04)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.01"
            value={asset.growth_rate ?? 0}
            onChange={(e) => onChange({ growth_rate: Number(e.target.value) })}
            style={inputStyle}
          />
        </label>
      </div>
      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Owner</span>
        <ResponsiveSelect<string>
          value={asset.ownerPersonDraftId ?? ""}
          onChange={(v) => onChange({ ownerPersonDraftId: v === "" ? null : v })}
          options={ownerOptions}
          label="Owner"
        />
      </label>
      {extra}
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
