import { useEffect, useRef, useState } from "react";

import { NumericInput } from "../../components/NumericInput";

import {
  useCreatePerson,
  useDeletePerson,
  usePeople,
  usePlan,
  useUpdatePerson,
  useUpdatePlan,
} from "../../api/hooks";
import type { FilingStatus, Person, PersonCreate } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { EmptyState } from "../../components/EmptyState";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { EditModal } from "../../components/EditModal";
import { useSoftDelete } from "../../lib/useSoftDelete";

type FormState = {
  name: string;
  dob: string;
  is_primary: boolean;
  life_expectancy: number;
  retirement_age: number | "";
  claims_rent_credit: boolean;
};

const blankForm: FormState = {
  name: "",
  dob: "1990-01-01",
  is_primary: false,
  life_expectancy: 90,
  retirement_age: 66,
  claims_rent_credit: false,
};

function fromPerson(p: Person): FormState {
  return {
    name: p.name,
    dob: p.dob,
    is_primary: p.is_primary,
    life_expectancy: p.life_expectancy,
    retirement_age: p.retirement_age ?? "",
    claims_rent_credit: p.claims_rent_credit ?? false,
  };
}

export function PeoplePane({ planId }: { planId: number }) {
  const { data: people, isLoading } = usePeople(planId);
  const { data: plan } = usePlan(planId);
  const create = useCreatePerson(planId);
  const update = useUpdatePerson(planId);
  const del = useDeletePerson(planId);
  const updatePlan = useUpdatePlan(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  const softDelete = useSoftDelete<Person, PersonCreate>({
    describe: (p) => `"${p.name}"`,
    toPayload: (p) => ({
      name: p.name,
      dob: p.dob,
      is_primary: p.is_primary,
      life_expectancy: p.life_expectancy,
      retirement_age: p.retirement_age,
      claims_rent_credit: p.claims_rent_credit,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
    warnCascade: true,
  });

  useEffect(() => {
    if (editingId === null || !people) return;
    const row = people.find((p) => p.id === editingId);
    if (row) setEditForm(fromPerson(row));
  }, [editingId, people]);

  const buildPayload = (f: FormState) => ({
    name: f.name.trim(),
    dob: f.dob,
    is_primary: f.is_primary,
    life_expectancy: f.life_expectancy,
    retirement_age: f.retirement_age === "" ? null : Number(f.retirement_age),
    claims_rent_credit: f.claims_rent_credit,
  });

  const onFilingStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value;
    const next: FilingStatus | null = v === "auto" ? null : (v as FilingStatus);
    updatePlan.mutate({ filing_status: next });
  };

  const autoStatus = (people?.length ?? 0) >= 2 ? "married" : "single";
  const filingValue = plan?.filing_status ?? "auto";

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync(buildPayload(form));
    setForm(blankForm);
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim()) return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>
          Household
          <HelpTip>
            Filing status drives which income-tax band and which personal credit each person uses.
            "Auto" picks single for a 1-person plan and married for 2+. Override to "Cohabiting" if
            you live with a partner but aren't married or in a civil partnership — Irish Revenue
            taxes cohabiting couples individually (no joint band, no married credit).
          </HelpTip>
        </h3>
        <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
          <div className="field" style={{ flex: 1, maxWidth: 320 }}>
            <label>Filing status</label>
            <select value={filingValue} onChange={onFilingStatusChange} disabled={updatePlan.isPending}>
              <option value="auto">Auto</option>
              <option value="single">Single</option>
              <option value="married">Married / civil partnership</option>
              <option value="cohabiting">Cohabiting (taxed as singles)</option>
            </select>
          </div>
          <div style={{ paddingBottom: 8 }}>
            <span
              style={{
                display: "inline-block",
                padding: "4px 10px",
                borderRadius: 999,
                background: filingValue === "auto" ? "#e0f2fe" : "#dbeafe",
                color: "#1e3a8a",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              Currently taxed as:{" "}
              {(filingValue === "auto" ? autoStatus : filingValue) === "married"
                ? "Married (joint band)"
                : (filingValue === "auto" ? autoStatus : filingValue) === "cohabiting"
                ? "Cohabiting (each as single)"
                : "Single"}
              {filingValue === "auto" && " (auto)"}
            </span>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add person</h3>
        <form onSubmit={onSubmit}>
          <FormFields form={form} setForm={setForm} placeholderName="e.g. Aoife O'Brien" />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>People</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {people && people.length === 0 && (
          <EmptyState
            title="Add your first person to start a plan."
            hint="Meridian projects per-person income, tax, and pensions. Most plans are 1 or 2 adults; add dependants only if you want to model them separately."
          />
        )}
        {people && people.length > 0 && (
          <ResponsiveTable<Person>
            rows={people}
            getKey={(p) => p.id}
            cardTitle={(p) => p.name}
            columns={[
              { header: "Name", cell: (p) => p.name, hideOnMobile: true },
              { header: "DOB", cell: (p) => p.dob },
              { header: "Life expectancy", cell: (p) => p.life_expectancy },
              {
                header: "Retire @",
                cell: (p) => p.retirement_age ?? "—",
                thExtra: (
                  <HelpTip>
                    Age this person retires. At this age the engine crystallises their pension wrappers
                    (25% lump sum + 75% to ARF) and stops applying employer/PRSI charges to earnings.
                  </HelpTip>
                ),
              },
              {
                header: "Primary",
                cell: (p) => (p.is_primary ? "Yes" : ""),
                thExtra: (
                  <HelpTip>
                    Head of household. Currently used as the default owner of joint expenses and as the
                    anchor for joint-assessment tax bands when there are two adults in the plan.
                  </HelpTip>
                ),
              },
              {
                header: "Rent credit",
                cell: (p) => (p.claims_rent_credit ? "Yes" : ""),
                thExtra: (
                  <HelpTip>
                    Per-person Irish Rent Tax Credit (€1,000/yr). Apply only to renters paying for
                    their primary residence.
                  </HelpTip>
                ),
              },
            ]}
            renderActions={(p) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(p.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDelete(p, p.id)}>
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
        title="Edit person"
        footer={
          <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
            <button
              className="btn btn-secondary"
              onClick={() => setEditingId(null)}
              type="button"
            >
              Cancel
            </button>
            <button className="btn" onClick={onSaveEdit} disabled={update.isPending}>
              Save
            </button>
          </div>
        }
      >
        <FormFields form={editForm} setForm={setEditForm} />
      </EditModal>
    </div>
  );
}

let _formFieldsSeq = 0;

function FormFields({
  form,
  setForm,
  placeholderName,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
  placeholderName?: string;
}) {
  // Module-level counter gives a stable unique id for label/htmlFor pairing
  // across two simultaneous FormFields (Add + Edit modal) without pulling in
  // useId-specific React quirks for SSR.
  const idRef = useRef<number | null>(null);
  if (idRef.current === null) idRef.current = ++_formFieldsSeq;
  const prefix = `person-form-${idRef.current}`;
  const nameMissing = !form.name.trim();

  return (
    <div className="row" style={{ alignItems: "flex-end" }}>
      <div className="field" style={{ flex: 2 }}>
        <label htmlFor={`${prefix}-name`}>Name</label>
        <input
          id={`${prefix}-name`}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder={placeholderName}
          required
          aria-required="true"
          aria-invalid={nameMissing || undefined}
        />
      </div>
      <div className="field" style={{ flex: 1 }}>
        <label htmlFor={`${prefix}-dob`}>Date of birth</label>
        <input
          id={`${prefix}-dob`}
          type="date"
          value={form.dob}
          onChange={(e) => setForm({ ...form, dob: e.target.value })}
          required
          aria-required="true"
        />
      </div>
      <div className="field" style={{ flex: 1 }}>
        <label>Life expectancy</label>
        <NumericInput
          integer
          value={form.life_expectancy}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, life_expectancy: v })}
        />
      </div>
      <div className="field" style={{ flex: 1 }}>
        <label>Retirement age</label>
        <NumericInput
          integer
          placeholder="—"
          value={form.retirement_age === "" ? NaN : form.retirement_age}
          onChange={(v) => setForm({ ...form, retirement_age: Number.isFinite(v) ? v : "" })}
        />
      </div>
      <div className="field" style={{ flex: 0 }}>
        <label>
          Primary
          <HelpTip>Head of household. Default owner for joint expenses.</HelpTip>
        </label>
        <input
          type="checkbox"
          checked={form.is_primary}
          onChange={(e) => setForm({ ...form, is_primary: e.target.checked })}
        />
      </div>
      <div className="field" style={{ flex: 0 }}>
        <label>
          Rent credit
          <HelpTip>
            Tick if this person pays rent on their primary residence (or for digs near work).
            Reduces their income tax by €1,000/yr (Irish Rent Tax Credit).
          </HelpTip>
        </label>
        <input
          type="checkbox"
          checked={form.claims_rent_credit}
          onChange={(e) => setForm({ ...form, claims_rent_credit: e.target.checked })}
        />
      </div>
    </div>
  );
}
