import { useEffect, useMemo, useState } from "react";

import {
  useCreateLiability,
  useDeleteLiability,
  useLiabilities,
  useUpdateLiability,
} from "../../api/hooks";
import type { Liability, LiabilityCreate, LiabilityKind } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { NumericInput } from "../../components/NumericInput";
import { EmptyState } from "../../components/EmptyState";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { EditModal } from "../../components/EditModal";
import { fmtMoney } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

const KINDS: { value: LiabilityKind; label: string }[] = [
  { value: "mortgage", label: "Mortgage" },
  { value: "loan", label: "Loan" },
];

function amortisedPayment(principal: number, annualRate: number, termMonths: number): number {
  if (termMonths <= 0) return 0;
  if (annualRate <= 0) return principal / termMonths;
  const r = annualRate / 12;
  return (principal * r) / (1 - Math.pow(1 + r, -termMonths));
}

type FormState = {
  name: string;
  kind: LiabilityKind;
  principal: number;
  interest_rate: number;
  term_months: number;
  start_year: number;
  monthly_overpayment: number;
};

const blankForm: FormState = {
  name: "Mortgage",
  kind: "mortgage",
  principal: 250_000,
  interest_rate: 0.04,
  term_months: 300,
  start_year: 2026,
  monthly_overpayment: 0,
};

function fromLiability(l: Liability): FormState {
  return {
    name: l.name,
    kind: l.kind,
    principal: l.principal,
    interest_rate: l.interest_rate,
    term_months: l.term_months,
    start_year: l.start_year,
    monthly_overpayment: l.monthly_overpayment ?? 0,
  };
}

export function LiabilitiesPane({ planId }: { planId: number }) {
  const { data, isLoading } = useLiabilities(planId);
  const create = useCreateLiability(planId);
  const update = useUpdateLiability(planId);
  const del = useDeleteLiability(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  const softDelete = useSoftDelete<Liability, LiabilityCreate>({
    describe: (l) => `liability "${l.name}"`,
    toPayload: (l) => ({
      name: l.name,
      kind: l.kind,
      principal: l.principal,
      interest_rate: l.interest_rate,
      term_months: l.term_months,
      start_year: l.start_year,
      monthly_payment: l.monthly_payment,
      monthly_overpayment: l.monthly_overpayment,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !data) return;
    const row = data.find((d) => d.id === editingId);
    if (row) setEditForm(fromLiability(row));
  }, [editingId, data]);

  const previewPayment = useMemo(
    () => amortisedPayment(form.principal, form.interest_rate, form.term_months),
    [form.principal, form.interest_rate, form.term_months],
  );
  const editPreview = useMemo(
    () => amortisedPayment(editForm.principal, editForm.interest_rate, editForm.term_months),
    [editForm.principal, editForm.interest_rate, editForm.term_months],
  );

  const buildPayload = (f: FormState, includeMonthly: boolean) => {
    const base = {
      name: f.name.trim(),
      kind: f.kind,
      principal: f.principal,
      interest_rate: f.interest_rate,
      term_months: f.term_months,
      start_year: f.start_year,
      monthly_overpayment: Math.max(0, f.monthly_overpayment),
    };
    return includeMonthly
      ? { ...base, monthly_payment: amortisedPayment(f.principal, f.interest_rate, f.term_months) }
      : base;
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync({ ...buildPayload(form, false), monthly_payment: null });
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim()) return;
    await update.mutateAsync({
      id: editingId,
      body: buildPayload(editForm, true),
    });
    setEditingId(null);
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add liability</h3>
        <p className="muted" style={{ marginTop: -4, fontSize: 13 }}>
          Add mortgages and loans here only — the engine amortises the balance and adds each
          repayment to your expenses automatically. Don't also add the repayment as an expense.
        </p>
        <form onSubmit={onSubmit}>
          <FormFields form={form} setForm={setForm} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
          <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
            Calculated monthly payment: <strong>{fmtMoney(previewPayment)}</strong>
          </p>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Liabilities</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {data && data.length === 0 && (
          <EmptyState
            title="No mortgages or loans? Skip this tab."
            hint="Add a mortgage or loan if you carry debt — the engine amortises the payments and reduces your net worth by the outstanding balance each year."
          />
        )}
        {data && data.length > 0 && (
          <ResponsiveTable<Liability>
            rows={data}
            getKey={(l) => l.id}
            cardTitle={(l) => l.name}
            columns={[
              { header: "Name", cell: (l) => l.name, hideOnMobile: true },
              { header: "Type", cell: (l) => <span className="muted">{l.kind}</span> },
              { header: "Principal", cell: (l) => fmtMoney(l.principal) },
              { header: "Rate", cell: (l) => `${(l.interest_rate * 100).toFixed(2)}%` },
              {
                header: "Term",
                cell: (l) => `${Math.round(l.term_months / 12)}y (${l.term_months}m)`,
              },
              { header: "Monthly", cell: (l) => fmtMoney(l.monthly_payment) },
              {
                header: "Overpay",
                cell: (l) => (l.monthly_overpayment > 0 ? fmtMoney(l.monthly_overpayment) : "—"),
              },
            ]}
            renderActions={(l) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(l.id)}
                >
                  Edit
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => softDelete(l, l.id)}
                >
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
        title="Edit liability"
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
        <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
          New monthly payment: <strong>{fmtMoney(editPreview)}</strong>
        </p>
      </EditModal>
    </div>
  );
}

function TermInput({
  months,
  onChange,
}: {
  months: number;
  onChange: (months: number) => void;
}) {
  const [unit, setUnit] = useState<"years" | "months">(months % 12 === 0 ? "years" : "months");
  const displayValue =
    unit === "years" ? (months % 12 === 0 ? months / 12 : Math.round((months / 12) * 10) / 10) : months;
  return (
    <div className="field" style={{ flex: 1, minWidth: 140 }}>
      <label>
        Term
        <button
          type="button"
          onClick={() => setUnit(unit === "years" ? "months" : "years")}
          style={{
            marginLeft: 6,
            fontSize: 11,
            background: "transparent",
            border: "1px solid #cbd5e1",
            borderRadius: 4,
            padding: "1px 6px",
            cursor: "pointer",
            color: "#475569",
          }}
        >
          {unit === "years" ? "yrs" : "mo"} ⇄
        </button>
      </label>
      <NumericInput
        integer={unit === "months"}
        value={displayValue}
        onChange={(v) => {
          if (!Number.isFinite(v)) return;
          onChange(unit === "years" ? Math.round(v * 12) : Math.trunc(v));
        }}
      />
    </div>
  );
}

function FormFields({
  form,
  setForm,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
}) {
  return (
    <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
      <div className="field" style={{ flex: 1, minWidth: 140 }}>
        <label>Type</label>
        <select
          value={form.kind}
          onChange={(e) => setForm({ ...form, kind: e.target.value as LiabilityKind })}
        >
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
      </div>
      <div className="field" style={{ flex: 2, minWidth: 180 }}>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 120 }}>
        <label>Principal (€)</label>
        <NumericInput
          value={form.principal}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, principal: v })}
        />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 100 }}>
        <label>Rate %</label>
        <NumericInput
          value={form.interest_rate * 100}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, interest_rate: v / 100 })}
        />
      </div>
      <TermInput
        months={form.term_months}
        onChange={(months) => setForm({ ...form, term_months: months })}
      />

      <div className="field" style={{ flex: 1, minWidth: 100 }}>
        <label>Start year</label>
        <NumericInput
          integer
          value={form.start_year}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, start_year: v })}
        />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 130 }}>
        <label>
          Overpayment €/mo
          <HelpTip>
            Extra €/mo paid on top of the contracted monthly payment. Goes straight to capital,
            so the loan ends earlier. Banks typically allow up to ±10% of your contracted payment
            fee-free; check your specific terms.
          </HelpTip>
        </label>
        <NumericInput
          value={form.monthly_overpayment}
          onChange={(v) =>
            Number.isFinite(v) && setForm({ ...form, monthly_overpayment: Math.max(0, v) })
          }
        />
      </div>
    </div>
  );
}
