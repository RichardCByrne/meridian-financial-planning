import { useEffect, useState } from "react";

import {
  useBenefits,
  useCreateBenefit,
  useDeleteBenefit,
  usePeople,
  useUpdateBenefit,
} from "../../api/hooks";
import type { Benefit, BenefitCreate, BenefitKind } from "../../api/types";
import { EditModal } from "../../components/EditModal";
import { EmptyState } from "../../components/EmptyState";
import { HelpTip } from "../../components/HelpTip";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { fmtMoney, fmtPctDisplay } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

const KIND_LABELS: Record<BenefitKind, string> = {
  medical_insurance: "Medical insurance",
  company_car: "Company car",
  company_van: "Company van",
  preferential_loan: "Preferential loan",
  other: "Other",
};

const KIND_OPTIONS = Object.entries(KIND_LABELS) as [BenefitKind, string][];

type FormState = {
  person_id: number | "";
  kind: BenefitKind;
  name: string;
  start_year: number;
  end_year: number | "";
  escalation_rate: number;
  amount: number;
  omv: number;
  rate: number;
  loan_is_qualifying: boolean;
  relief_adults: number;
  relief_children: number;
};

const blankForm: FormState = {
  person_id: "",
  kind: "medical_insurance",
  name: "",
  start_year: new Date().getFullYear(),
  end_year: "",
  escalation_rate: 0,
  amount: 0,
  omv: 0,
  rate: 0,
  loan_is_qualifying: false,
  relief_adults: 1,
  relief_children: 0,
};

function fromBenefit(b: Benefit): FormState {
  return {
    person_id: b.person_id,
    kind: b.kind,
    name: b.name,
    start_year: b.start_year,
    end_year: b.end_year ?? "",
    escalation_rate: b.escalation_rate,
    amount: b.amount,
    omv: b.omv,
    rate: b.rate,
    loan_is_qualifying: b.loan_is_qualifying,
    relief_adults: b.relief_adults,
    relief_children: b.relief_children,
  };
}

export function BenefitsPane({ planId }: { planId: number }) {
  const { data: people } = usePeople(planId);
  const { data: benefits, isLoading } = useBenefits(planId);
  const create = useCreateBenefit(planId);
  const update = useUpdateBenefit(planId);
  const del = useDeleteBenefit(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  // Default the new-benefit person selector to the first person once loaded.
  useEffect(() => {
    if (form.person_id === "" && people && people.length > 0) {
      setForm((f) => ({ ...f, person_id: people[0].id }));
    }
  }, [people, form.person_id]);

  const softDelete = useSoftDelete<Benefit, BenefitCreate>({
    describe: (b) => `"${b.name}"`,
    toPayload: (b) => ({
      person_id: b.person_id,
      kind: b.kind,
      name: b.name,
      start_year: b.start_year,
      end_year: b.end_year,
      escalation_rate: b.escalation_rate,
      amount: b.amount,
      omv: b.omv,
      rate: b.rate,
      loan_is_qualifying: b.loan_is_qualifying,
      relief_adults: b.relief_adults,
      relief_children: b.relief_children,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !benefits) return;
    const row = benefits.find((b) => b.id === editingId);
    if (row) setEditForm(fromBenefit(row));
  }, [editingId, benefits]);

  const buildPayload = (f: FormState): BenefitCreate => ({
    person_id: f.person_id === "" ? 0 : Number(f.person_id),
    kind: f.kind,
    name: f.name.trim(),
    start_year: f.start_year,
    end_year: f.end_year === "" ? null : Number(f.end_year),
    escalation_rate: f.escalation_rate,
    amount: f.amount,
    omv: f.omv,
    rate: f.rate,
    loan_is_qualifying: f.loan_is_qualifying,
    relief_adults: f.relief_adults,
    relief_children: f.relief_children,
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || form.person_id === "") return;
    await create.mutateAsync(buildPayload(form));
    setForm({ ...blankForm, person_id: form.person_id, kind: form.kind });
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim() || editForm.person_id === "") return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  const personName = (id: number) =>
    people?.find((p) => p.id === id)?.name ?? "(removed)";

  const summarise = (b: Benefit): string => {
    switch (b.kind) {
      case "company_car":
        return b.omv > 0
          ? `OMV ${fmtMoney(b.omv)} × ${b.rate > 0 ? fmtPctDisplay(b.rate) : "default"}`
          : fmtMoney(b.amount);
      case "company_van":
        return b.omv > 0 ? `OMV ${fmtMoney(b.omv)} × 8%` : fmtMoney(b.amount);
      case "preferential_loan":
        return `${fmtMoney(b.amount)} @ ${fmtPctDisplay(b.rate)}${b.loan_is_qualifying ? " (home)" : ""}`;
      default:
        return fmtMoney(b.amount);
    }
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>
          Add benefit-in-kind
          <HelpTip>
            Employer-provided perks (medical insurance, company car/van, preferential loans).
            The cash equivalent is taxed as notional pay — income tax, USC and PRSI — but is
            never received as cash and is not a household expense. Employer-paid medical
            insurance also earns the 20% relief credit (capped €1,000/adult, €500/child),
            because tax relief at source isn't granted when the employer pays.
          </HelpTip>
        </h3>
        <form onSubmit={onSubmit}>
          <BenefitFields form={form} setForm={setForm} people={people ?? []} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Benefits-in-kind</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {benefits && benefits.length === 0 && (
          <EmptyState
            title="No benefits-in-kind yet."
            hint="Add employer-paid medical insurance, a company car, or other taxable perks to see their effect on tax."
          />
        )}
        {benefits && benefits.length > 0 && (
          <ResponsiveTable<Benefit>
            rows={benefits}
            getKey={(b) => b.id}
            cardTitle={(b) => b.name}
            columns={[
              { header: "Name", cell: (b) => b.name, hideOnMobile: true },
              { header: "Person", cell: (b) => personName(b.person_id) },
              { header: "Kind", cell: (b) => KIND_LABELS[b.kind] },
              { header: "Value", cell: (b) => summarise(b) },
              {
                header: "Years",
                cell: (b) => `${b.start_year}–${b.end_year ?? "∞"}`,
              },
            ]}
            renderActions={(b) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(b.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDelete(b, b.id)}>
                  Remove
                </button>
              </>
            )}
          />
        )}
      </div>

      <EditModal
        open={editingId !== null}
        onClose={() => setEditingId(null)}
        title="Edit benefit"
        footer={
          <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={() => setEditingId(null)} type="button">
              Cancel
            </button>
            <button className="btn" onClick={onSaveEdit} disabled={update.isPending}>
              Save
            </button>
          </div>
        }
      >
        <BenefitFields form={editForm} setForm={setEditForm} people={people ?? []} />
      </EditModal>
    </div>
  );
}

function BenefitFields({
  form,
  setForm,
  people,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
  people: { id: number; name: string }[];
}) {
  const isCar = form.kind === "company_car";
  const isVan = form.kind === "company_van";
  const isLoan = form.kind === "preferential_loan";
  const isMedical = form.kind === "medical_insurance";
  const usesAmount = !isCar && !isVan; // medical / other / loan all use `amount`

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "2 1 200px", minWidth: 180 }}>
          <label>Name</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. VHI health cover"
            required
          />
        </div>
        <div className="field" style={{ flex: "1 1 150px", minWidth: 150 }}>
          <label>Person</label>
          <select
            value={form.person_id}
            onChange={(e) =>
              setForm({ ...form, person_id: e.target.value === "" ? "" : Number(e.target.value) })
            }
          >
            <option value="">— Select —</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ flex: "1 1 160px", minWidth: 160 }}>
          <label>Kind</label>
          <select
            value={form.kind}
            onChange={(e) => setForm({ ...form, kind: e.target.value as BenefitKind })}
          >
            {KIND_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        {usesAmount && (
          <div className="field" style={{ flex: "1 1 160px", minWidth: 160 }}>
            <label>
              {isLoan ? "Loan balance (€)" : isMedical ? "Annual premium (€)" : "Annual value (€)"}
            </label>
            <input
              type="number"
              min={0}
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
            />
          </div>
        )}
        {(isCar || isVan) && (
          <div className="field" style={{ flex: "1 1 160px", minWidth: 160 }}>
            <label>
              Original Market Value (€)
              <HelpTip>List price when new. Cash equivalent = OMV × the BIK percentage.</HelpTip>
            </label>
            <input
              type="number"
              min={0}
              value={form.omv}
              onChange={(e) => setForm({ ...form, omv: Number(e.target.value) })}
            />
          </div>
        )}
        {isCar && (
          <div className="field" style={{ flex: "1 1 140px", minWidth: 140 }}>
            <label>
              BIK rate (%)
              <HelpTip>Leave 0 to use the default mid-band (22.5%). The 2023+ regime bands this 6%–37.5% by CO₂ and mileage.</HelpTip>
            </label>
            <input
              type="number"
              min={0}
              step={0.5}
              value={form.rate * 100}
              onChange={(e) => setForm({ ...form, rate: Number(e.target.value) / 100 })}
            />
          </div>
        )}
        {isLoan && (
          <>
            <div className="field" style={{ flex: "1 1 140px", minWidth: 140 }}>
              <label>
                Rate charged (%)
                <HelpTip>The interest rate the employer charges. BIK = balance × (specified rate − this). Specified rates: 4% home loan, 13.5% other.</HelpTip>
              </label>
              <input
                type="number"
                min={0}
                step={0.1}
                value={form.rate * 100}
                onChange={(e) => setForm({ ...form, rate: Number(e.target.value) / 100 })}
              />
            </div>
            <div className="field" style={{ flex: "0 1 auto", minWidth: 140 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="checkbox"
                  checked={form.loan_is_qualifying}
                  onChange={(e) => setForm({ ...form, loan_is_qualifying: e.target.checked })}
                  style={{ width: "auto" }}
                />
                Qualifying home loan
              </label>
            </div>
          </>
        )}
      </div>

      {isMedical && (
        <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "1 1 120px", minWidth: 120 }}>
            <label>
              Adults covered
              <HelpTip>Relief is 20% of the premium, capped at €1,000 per adult and €500 per child.</HelpTip>
            </label>
            <input
              type="number"
              min={0}
              value={form.relief_adults}
              onChange={(e) => setForm({ ...form, relief_adults: Number(e.target.value) })}
            />
          </div>
          <div className="field" style={{ flex: "1 1 120px", minWidth: 120 }}>
            <label>Children covered</label>
            <input
              type="number"
              min={0}
              value={form.relief_children}
              onChange={(e) => setForm({ ...form, relief_children: Number(e.target.value) })}
            />
          </div>
        </div>
      )}

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div className="field" style={{ flex: "1 1 110px", minWidth: 110 }}>
          <label>Start year</label>
          <input
            type="number"
            value={form.start_year}
            onChange={(e) => setForm({ ...form, start_year: Number(e.target.value) })}
          />
        </div>
        <div className="field" style={{ flex: "1 1 110px", minWidth: 110 }}>
          <label>End year</label>
          <input
            type="number"
            value={form.end_year}
            placeholder="∞"
            onChange={(e) =>
              setForm({ ...form, end_year: e.target.value === "" ? "" : Number(e.target.value) })
            }
          />
        </div>
        <div className="field" style={{ flex: "1 1 130px", minWidth: 130 }}>
          <label>Escalation (%)</label>
          <input
            type="number"
            step={0.5}
            value={form.escalation_rate * 100}
            onChange={(e) => setForm({ ...form, escalation_rate: Number(e.target.value) / 100 })}
          />
        </div>
      </div>
    </div>
  );
}
