import type { BenefitKind } from "../../../api/types";
import type { BenefitDraft } from "../../../wizard/store";
import { useWizard } from "../../../wizard/store";
import { HelpTip } from "../../HelpTip";
import { NumericInput } from "../../NumericInput";
import { ResponsiveSelect } from "../../ResponsiveSelect";

const KIND_OPTIONS: { value: BenefitKind; label: string }[] = [
  { value: "medical_insurance", label: "Medical insurance" },
  { value: "company_car", label: "Company car" },
  { value: "company_van", label: "Company van" },
  { value: "preferential_loan", label: "Preferential loan" },
  { value: "other", label: "Other" },
];

export function BenefitsStep() {
  const benefits = useWizard((s) => s.benefits);
  const people = useWizard((s) => s.people);
  const plan = useWizard((s) => s.plan);
  const addBenefit = useWizard((s) => s.addBenefit);
  const updateBenefit = useWizard((s) => s.updateBenefit);
  const removeBenefit = useWizard((s) => s.removeBenefit);

  const baseYear = plan.base_year ?? new Date().getFullYear();
  const personOptions = people.map((p) => ({ value: p.draftId, label: p.name || "Unnamed" }));

  const onAdd = () =>
    addBenefit({
      personDraftId: people[0]?.draftId ?? "",
      kind: "medical_insurance",
      name: "Employer health cover",
      start_year: baseYear,
      end_year: null,
      escalation_rate: 0.03,
      amount: 2_000,
      omv: 0,
      rate: 0,
      loan_is_qualifying: false,
      relief_adults: 1,
      relief_children: 0,
    });

  if (people.length === 0) {
    return (
      <div className="muted" style={{ color: "#64748b" }}>
        Add a person first — benefits-in-kind are attached to an employee.
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="muted" style={{ color: "#64748b" }}>
        Optional. Employer benefits-in-kind (medical insurance, company car/van, preferential loan)
        are taxed as notional pay — they raise IT/USC/PRSI but aren't received as cash. Skip if none.
      </div>
      {benefits.map((b) => (
        <BenefitRow
          key={b.draftId}
          benefit={b}
          personOptions={personOptions}
          onChange={(patch) => updateBenefit(b.draftId, patch)}
          onRemove={() => removeBenefit(b.draftId)}
        />
      ))}
      <button type="button" className="btn btn-secondary" onClick={onAdd} style={{ minHeight: 44 }}>
        + Add benefit-in-kind
      </button>
    </div>
  );
}

function BenefitRow({
  benefit,
  personOptions,
  onChange,
  onRemove,
}: {
  benefit: BenefitDraft;
  personOptions: { value: string; label: string }[];
  onChange: (patch: Partial<BenefitDraft>) => void;
  onRemove: () => void;
}) {
  const kind = benefit.kind;
  const isCar = kind === "company_car";
  const isVan = kind === "company_van";
  const isLoan = kind === "preferential_loan";
  const isMedical = kind === "medical_insurance";
  const usesAmount = !isCar && !isVan;
  const num = (v: number) => (Number.isFinite(v) ? Math.max(0, v) : 0);

  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Person</span>
          <ResponsiveSelect<string>
            value={benefit.personDraftId}
            onChange={(v) => onChange({ personDraftId: v })}
            options={personOptions}
            label="Person"
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Kind</span>
          <ResponsiveSelect<BenefitKind>
            value={kind}
            onChange={(v) => onChange({ kind: v })}
            options={KIND_OPTIONS}
            label="Benefit kind"
          />
        </label>
      </div>

      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Name</span>
        <input
          value={benefit.name}
          onChange={(e) => onChange({ name: e.target.value })}
          style={inputStyle}
        />
      </label>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {usesAmount && (
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontWeight: 600 }}>
              {isLoan ? "Loan balance (€)" : isMedical ? "Annual premium (€)" : "Annual value (€)"}
            </span>
            <NumericInput
              value={benefit.amount ?? 0}
              onChange={(v) => onChange({ amount: num(v) })}
              style={inputStyle}
            />
          </label>
        )}
        {(isCar || isVan) && (
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
              Original Market Value (€)
              <HelpTip>List price when new. Cash equivalent = OMV × the BIK percentage.</HelpTip>
            </span>
            <NumericInput
              value={benefit.omv ?? 0}
              onChange={(v) => onChange({ omv: num(v) })}
              style={inputStyle}
            />
          </label>
        )}
        {(isCar || isLoan) && (
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
              {isCar ? "BIK rate %" : "Rate charged %"}
              <HelpTip>
                {isCar
                  ? "Leave 0 to use the default mid-band (the 2023+ regime bands this by CO₂ and mileage)."
                  : "The rate the employer charges. BIK = balance × (specified rate − this)."}
              </HelpTip>
            </span>
            <input
              type="number"
              step="0.1"
              value={(benefit.rate ?? 0) * 100}
              onChange={(e) => onChange({ rate: Number(e.target.value) / 100 })}
              style={inputStyle}
            />
          </label>
        )}
      </div>

      {isLoan && (
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={benefit.loan_is_qualifying ?? false}
            onChange={(e) => onChange({ loan_is_qualifying: e.target.checked })}
          />
          Qualifying home loan
        </label>
      )}

      {isMedical && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 }}>
              Adults covered
              <HelpTip>Relief is 20% of the premium, capped at €1,000 per adult and €500 per child.</HelpTip>
            </span>
            <NumericInput
              integer
              value={benefit.relief_adults ?? 1}
              onChange={(v) => onChange({ relief_adults: Number.isFinite(v) ? v : 1 })}
              style={inputStyle}
            />
          </label>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ fontWeight: 600 }}>Children covered</span>
            <NumericInput
              integer
              value={benefit.relief_children ?? 0}
              onChange={(v) => onChange({ relief_children: Number.isFinite(v) ? v : 0 })}
              style={inputStyle}
            />
          </label>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Start year</span>
          <NumericInput
            integer
            value={benefit.start_year}
            onChange={(v) => onChange({ start_year: Number.isFinite(v) ? v : benefit.start_year })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>End year</span>
          <NumericInput
            integer
            value={benefit.end_year ?? NaN}
            onChange={(v) => onChange({ end_year: Number.isFinite(v) ? v : null })}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Escalation %</span>
          <input
            type="number"
            step="0.5"
            value={(benefit.escalation_rate ?? 0) * 100}
            onChange={(e) => onChange({ escalation_rate: Number(e.target.value) / 100 })}
            style={inputStyle}
          />
        </label>
      </div>

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
