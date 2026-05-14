import { useWizard, type DraftId, type PersonDraft } from "../../../wizard/store";
import { validatePerson } from "../../../wizard/validation";
import { NumericInput } from "../../NumericInput";

export function PeopleStep() {
  const people = useWizard((s) => s.people);
  const addPerson = useWizard((s) => s.addPerson);
  const updatePerson = useWizard((s) => s.updatePerson);
  const removePerson = useWizard((s) => s.removePerson);

  const onAdd = () => {
    const isFirst = people.length === 0;
    addPerson({
      name: "",
      dob: "1990-01-01",
      is_primary: isFirst,
      life_expectancy: 90,
      retirement_age: 66,
      claims_rent_credit: false,
      lump_sum_pct: 0.25,
      prsi_weeks_at_base_year: 2080,
      homecaring_weeks_at_base_year: 0,
      arf_target_drawdown_pct: null,
    });
  };

  const onPrimary = (id: DraftId) => {
    people.forEach((p) => updatePerson(p.draftId, { is_primary: p.draftId === id }));
  };

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {people.length === 0 && (
        <div className="muted" style={{ color: "#64748b" }}>
          Add the primary plan holder, then any spouse or partner.
        </div>
      )}

      {people.map((p) => (
        <PersonRow
          key={p.draftId}
          person={p}
          onChange={(patch) => updatePerson(p.draftId, patch)}
          onPrimary={() => onPrimary(p.draftId)}
          onRemove={() => removePerson(p.draftId)}
        />
      ))}

      <button
        type="button"
        className="btn btn-secondary"
        onClick={onAdd}
        style={{ minHeight: 44 }}
      >
        + Add person
      </button>
    </div>
  );
}

function PersonRow({
  person,
  onChange,
  onPrimary,
  onRemove,
}: {
  person: PersonDraft;
  onChange: (patch: Partial<PersonDraft>) => void;
  onPrimary: () => void;
  onRemove: () => void;
}) {
  const errs = validatePerson(person);
  return (
    <div className="card" style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Name</span>
          <input
            value={person.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="First Last"
            style={inputStyle}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ fontWeight: 600 }}>Date of birth</span>
          <input
            type="date"
            value={person.dob}
            onChange={(e) => onChange({ dob: e.target.value })}
            style={inputStyle}
          />
        </label>
      </div>

      <label style={{ display: "grid", gap: 4 }}>
        <span style={{ fontWeight: 600 }}>Retirement age</span>
        <NumericInput
          integer
          value={person.retirement_age ?? NaN}
          onChange={(v) => onChange({ retirement_age: Number.isFinite(v) ? v : null })}
          style={inputStyle}
        />
      </label>

      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="radio"
          name="is_primary"
          checked={person.is_primary}
          onChange={onPrimary}
        />
        <span>Primary plan holder</span>
      </label>

      {errs.length > 0 && (
        <div style={{ color: "#991b1b", fontSize: 13 }}>{errs.join(" · ")}</div>
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
