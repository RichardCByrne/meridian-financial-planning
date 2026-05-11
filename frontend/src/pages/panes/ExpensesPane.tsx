import { useEffect, useState } from "react";

import {
  useCreateExpense,
  useDeleteExpense,
  useExpenses,
  useUpdateExpense,
} from "../../api/hooks";
import type { Expense, ExpenseCategory, ExpenseCreate } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { EmptyState } from "../../components/EmptyState";
import { fmtPctDisplay } from "../../lib/format";
import { NumericInput } from "../../components/NumericInput";
import { TableSkeleton } from "../../components/Skeleton";
import { fmtMoney } from "../../lib/format";
import { useSoftDelete } from "../../lib/useSoftDelete";

const CATEGORIES: { value: ExpenseCategory; label: string; hint: string }[] = [
  {
    value: "basic",
    label: "Basic",
    hint: "Essential recurring spend (food, utilities, mortgage). Runs from start year to end year.",
  },
  {
    value: "discretionary",
    label: "Discretionary",
    hint: "Optional recurring spend (holidays, dining out). Same shape as basic but can be cut in tight years.",
  },
  {
    value: "single_year",
    label: "Single year (one-off)",
    hint: "Fires only in start_year and never again — perfect for a wedding, car, big trip, or any one-off cost. End_year and escalation are ignored.",
  },
  {
    value: "legacy",
    label: "Legacy",
    hint: "Recurring legacy / gifting provision.",
  },
];

type FormState = {
  name: string;
  category: ExpenseCategory;
  amount: number;
  start_year: number;
  end_year: number | "";
  escalation_rate: number;
};

const blankForm: FormState = {
  name: "Living expenses",
  category: "basic",
  amount: 30000,
  start_year: 2026,
  end_year: "",
  escalation_rate: 0.025,
};

function fromExpense(e: Expense): FormState {
  return {
    name: e.name,
    category: e.category,
    amount: e.amount,
    start_year: e.start_year,
    end_year: e.end_year ?? "",
    escalation_rate: e.escalation_rate,
  };
}

export function ExpensesPane({ planId }: { planId: number }) {
  const { data, isLoading } = useExpenses(planId);
  const create = useCreateExpense(planId);
  const update = useUpdateExpense(planId);
  const del = useDeleteExpense(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);

  const softDelete = useSoftDelete<Expense, ExpenseCreate>({
    describe: (e) => `expense "${e.name}"`,
    toPayload: (e) => ({
      name: e.name,
      category: e.category,
      amount: e.amount,
      start_year: e.start_year,
      end_year: e.end_year,
      escalation_rate: e.escalation_rate,
      owner_person_id: e.owner_person_id,
    }),
    remove: (id) => del.mutate(id),
    recreate: (payload) => create.mutate(payload),
  });

  useEffect(() => {
    if (editingId === null || !data) return;
    const row = data.find((d) => d.id === editingId);
    if (row) setEditForm(fromExpense(row));
  }, [editingId, data]);

  const buildPayload = (f: FormState) => ({
    name: f.name.trim(),
    category: f.category,
    amount: f.amount,
    start_year: f.start_year,
    end_year: f.end_year === "" ? null : Number(f.end_year),
    escalation_rate: f.escalation_rate,
  });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await create.mutateAsync(buildPayload(form));
  };

  const onSaveEdit = async () => {
    if (editingId === null || !editForm.name.trim()) return;
    await update.mutateAsync({ id: editingId, body: buildPayload(editForm) });
    setEditingId(null);
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add expense</h3>
        <form onSubmit={onSubmit}>
          <FormFields form={form} setForm={setForm} />
          <button type="submit" className="btn" disabled={create.isPending}>
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Expenses</h3>
        {isLoading && <TableSkeleton rows={3} />}
        {data && data.length === 0 && (
          <EmptyState
            title="Add at least one basic expense."
            hint="Without expenses the projection thinks you save 100% of net income — unrealistic. Start with a single 'Household running costs' line covering food, bills, and mortgage payments."
          />
        )}
        {data && data.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>
                  Category
                  <HelpTip>
                    Basic = essentials (rent, food). Discretionary = lifestyle (holidays).
                    Single-year = one-off (car). Legacy = gifts/charity.
                  </HelpTip>
                </th>
                <th>Amount / yr</th>
                <th>Years</th>
                <th>Esc.</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((e) =>
                editingId === e.id ? (
                  <tr key={e.id}>
                    <td colSpan={6}>
                      <FormFields form={editForm} setForm={setEditForm} />
                      <div className="row" style={{ marginTop: 8 }}>
                        <button className="btn" onClick={onSaveEdit} disabled={update.isPending}>
                          Save
                        </button>
                        <button
                          className="btn btn-secondary"
                          onClick={() => setEditingId(null)}
                          type="button"
                        >
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={e.id}>
                    <td>{e.name}</td>
                    <td className="muted">
                      {CATEGORIES.find((c) => c.value === e.category)?.label ?? e.category}
                    </td>
                    <td>{fmtMoney(e.amount)}</td>
                    <td>
                      {e.start_year}
                      {e.category === "single_year"
                        ? ""
                        : e.end_year
                        ? `–${e.end_year}`
                        : "→"}
                    </td>
                    <td>{fmtPctDisplay(e.escalation_rate)}</td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn btn-secondary"
                        style={{ marginRight: 6 }}
                        onClick={() => setEditingId(e.id)}
                      >
                        Edit
                      </button>
                      <button className="btn btn-secondary" onClick={() => softDelete(e, e.id)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        )}
      </div>
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
      <div className="field" style={{ flex: "2 1 160px" }}>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </div>
      <div className="field" style={{ flex: "1 1 120px" }}>
        <label>
          Category
          <HelpTip>{CATEGORIES.find((c) => c.value === form.category)?.hint}</HelpTip>
        </label>
        <select
          value={form.category}
          onChange={(e) => {
            const cat = e.target.value as ExpenseCategory;
            setForm({ ...form, category: cat, end_year: cat === "single_year" ? "" : form.end_year });
          }}
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <div className="field" style={{ flex: "1 1 100px" }}>
        <label>Amount / yr (€)</label>
        <NumericInput
          value={form.amount}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, amount: v })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>Start year</label>
        <NumericInput
          integer
          value={form.start_year}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, start_year: v })}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>End year</label>
        <NumericInput
          integer
          placeholder={form.category === "single_year" ? "n/a" : "—"}
          value={form.end_year === "" ? NaN : form.end_year}
          onChange={(v) => setForm({ ...form, end_year: Number.isFinite(v) ? v : "" })}
          disabled={form.category === "single_year"}
        />
      </div>
      <div className="field" style={{ flex: "1 1 80px" }}>
        <label>Inflation %</label>
        <NumericInput
          value={form.escalation_rate * 100}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, escalation_rate: v / 100 })
          }
        />
      </div>
    </div>
  );
}
