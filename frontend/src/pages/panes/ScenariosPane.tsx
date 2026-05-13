import { useEffect, useMemo, useState } from "react";

import {
  useAssets,
  useAssumptions,
  useCreateScenario,
  useDeleteScenario,
  useExpenses,
  useGoals,
  useLiabilities,
  usePeople,
  usePlan,
  useScenarios,
  useUpdateScenario,
} from "../../api/hooks";
import type {
  AddedExpense,
  AddedIncome,
  Expense,
  ExpenseCategory,
  IncomeKind,
  IncomeSource,
  Person,
  Scenario,
  ScenarioOverrides,
} from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { NumericInput } from "../../components/NumericInput";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { useToast } from "../../components/Toast";
import { useIncomeForPeople } from "../../lib/useIncomeForPeople";

type Bucket = keyof ScenarioOverrides;

type FieldDef = {
  name: string;
  label: string;
  kind: "number" | "percent" | "int" | "text";
  help?: string;
};

const FIELDS: Record<Bucket, FieldDef[]> = {
  people: [
    { name: "retirement_age", label: "Retirement age", kind: "int" },
    { name: "life_expectancy", label: "Life expectancy", kind: "int" },
  ],
  incomes: [
    { name: "gross_amount", label: "Gross amount (€)", kind: "number" },
    { name: "escalation_rate", label: "Escalation rate", kind: "percent" },
    { name: "pension_contribution_pct", label: "Pension %", kind: "percent" },
    { name: "employer_pension_contribution_pct", label: "Employer pension %", kind: "percent" },
    { name: "start_year", label: "Start year", kind: "int" },
    { name: "end_year", label: "End year", kind: "int" },
  ],
  expenses: [
    { name: "amount", label: "Amount (€)", kind: "number" },
    { name: "escalation_rate", label: "Escalation rate", kind: "percent" },
    { name: "start_year", label: "Start year", kind: "int" },
    { name: "end_year", label: "End year", kind: "int" },
  ],
  assets: [
    { name: "value", label: "Value (€)", kind: "number" },
    { name: "growth_rate", label: "Growth rate", kind: "percent" },
  ],
  liabilities: [
    { name: "interest_rate", label: "Interest rate", kind: "percent" },
    { name: "monthly_payment", label: "Monthly payment (€)", kind: "number" },
  ],
  goals: [
    { name: "target_amount", label: "Target amount (€)", kind: "number" },
    { name: "target_year", label: "Target year", kind: "int" },
  ],
  assumptions: [
    { name: "inflation_rate", label: "Inflation rate", kind: "percent" },
    { name: "default_growth_rate", label: "Default growth", kind: "percent" },
    { name: "property_growth_rate", label: "Property growth", kind: "percent" },
    { name: "earnings_growth", label: "Earnings growth", kind: "percent" },
    { name: "state_pension_age", label: "State pension age", kind: "int" },
    { name: "state_pension_annual_amount", label: "State pension €/yr", kind: "number" },
  ],
};

const BUCKET_LABELS: Record<Bucket, string> = {
  people: "Person",
  incomes: "Income",
  expenses: "Expense",
  assets: "Asset",
  liabilities: "Liability",
  goals: "Goal",
  assumptions: "Assumptions",
};

function formatValue(field: FieldDef, raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  if (field.kind === "percent") return `${(Number(raw) * 100).toFixed(2)}%`;
  if (field.kind === "number") return `€${Number(raw).toLocaleString()}`;
  return String(raw);
}

function parseValue(field: FieldDef, raw: string): unknown {
  if (raw === "") return null;
  if (field.kind === "percent" || field.kind === "number") return Number(raw);
  if (field.kind === "int") return Math.trunc(Number(raw));
  return raw;
}

export function ScenariosPane({ planId }: { planId: number }) {
  const { data: scenarios, isLoading } = useScenarios(planId);
  const { data: plan } = usePlan(planId);
  const create = useCreateScenario(planId);
  const update = useUpdateScenario(planId);
  const del = useDeleteScenario(planId);

  const [newName, setNewName] = useState("");
  const toast = useToast();

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>
          Scenarios
          <HelpTip>
            A scenario stores field-level overrides on top of the base plan. Compare two
            scenarios on the Compare tab to see the impact on net worth and tax.
          </HelpTip>
        </h3>
        <p className="muted">
          Two ways to diverge from the base plan:
          <br />
          <strong>1. Override an existing field</strong> (e.g. retire 5 years earlier; change inflation
          assumption) — pick bucket → target → field, then edit the value.
          <br />
          <strong>2. Add a new income or expense</strong> that doesn't exist in the base plan (e.g. a
          promotion in 2030, a one-off wedding cost, an inheritance).
          <br />
          The base plan stays untouched. Run <em>Compare</em> to see two scenarios side-by-side.
        </p>
        <form
          className="row"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!newName.trim()) return;
            await create.mutateAsync({ name: newName.trim(), overrides: {} });
            setNewName("");
          }}
        >
          <input
            placeholder="New scenario name (e.g. Retire at 60)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            style={{ padding: "8px 10px", border: "1px solid #cbd5e1", borderRadius: 6, flex: 1 }}
          />
          <button className="btn" type="submit" disabled={create.isPending}>
            Add scenario
          </button>
        </form>
      </div>

      {isLoading && <p className="muted">Loading…</p>}
      {scenarios && scenarios.length === 0 && (
        <div className="card">
          <p className="muted">No scenarios yet. Create one above.</p>
        </div>
      )}
      {scenarios?.map((s) => (
        <ScenarioCard
          key={s.id}
          planId={planId}
          baseYear={plan?.base_year ?? 2026}
          scenario={s}
          onSave={(overrides, name) =>
            update.mutateAsync({ id: s.id, body: { name, overrides } })
          }
          onDelete={() => softDeleteScenario(s, del.mutate, create.mutateAsync, toast)}
        />
      ))}
    </div>
  );
}

function softDeleteScenario(
  s: Scenario,
  doDelete: (id: number) => void,
  doCreate: (body: { name: string; overrides: ScenarioOverrides }) => Promise<unknown>,
  toast: ReturnType<typeof useToast>,
) {
  doDelete(s.id);
  toast.push({
    kind: "info",
    message: `Deleted scenario "${s.name}".`,
    autoDismissMs: 8000,
    action: {
      label: "Undo",
      onClick: () => {
        doCreate({ name: s.name, overrides: s.overrides });
      },
    },
  });
}

function ScenarioCard({
  planId,
  baseYear,
  scenario,
  onSave,
  onDelete,
}: {
  planId: number;
  baseYear: number;
  scenario: Scenario;
  onSave: (overrides: ScenarioOverrides, name: string) => Promise<unknown>;
  onDelete: () => void;
}) {
  const { data: people } = usePeople(planId);
  const { data: expenses } = useExpenses(planId);
  const { data: assets } = useAssets(planId);
  const { data: liabilities } = useLiabilities(planId);
  const { data: goals } = useGoals(planId);
  const { data: assumptions } = useAssumptions(planId);
  const { incomes } = useIncomeForPeople(people ?? []);

  const [name, setName] = useState(scenario.name);
  const [overrides, setOverrides] = useState<ScenarioOverrides>(scenario.overrides);
  const [showJson, setShowJson] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<"override" | "step" | "added">("override");

  // Reset local state only when we're switched to a *different* scenario id.
  // Background refetches on the same id no longer clobber in-flight edits.
  useEffect(() => {
    setName(scenario.name);
    setOverrides(scenario.overrides);
    setDirty(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario.id]);

  const instancesFor = (bucket: Bucket): { id: number; label: string }[] => {
    switch (bucket) {
      case "people":
        return (people ?? []).map((p) => ({ id: p.id, label: p.name }));
      case "incomes":
        return incomes.map((i) => ({
          id: i.id,
          label: `${i.name} (${people?.find((p) => p.id === i.person_id)?.name ?? "?"})`,
        }));
      case "expenses":
        return (expenses ?? []).map((e) => ({ id: e.id, label: e.name }));
      case "assets":
        return (assets ?? []).map((a) => ({ id: a.id, label: a.name }));
      case "liabilities":
        return (liabilities ?? []).map((l) => ({ id: l.id, label: l.name }));
      case "goals":
        return (goals ?? []).map((g) => ({ id: g.id, label: g.name }));
      case "assumptions":
        return assumptions ? [{ id: 0, label: "Plan assumptions" }] : [];
    }
  };

  const baseValueFor = (bucket: Bucket, id: number, fieldName: string): unknown => {
    if (bucket === "assumptions") return (assumptions as unknown as Record<string, unknown> | undefined)?.[fieldName];
    const list = ({
      people,
      incomes,
      expenses,
      assets,
      liabilities,
      goals,
    } as Record<Bucket, unknown[] | undefined>)[bucket];
    const row = (list ?? []).find((r) => (r as { id: number }).id === id) as
      | Record<string, unknown>
      | undefined;
    return row?.[fieldName];
  };

  const overrideRows = useMemo(() => {
    const rows: { bucket: Bucket; id: number; field: FieldDef; value: unknown }[] = [];
    for (const bucket of Object.keys(FIELDS) as Bucket[]) {
      if (bucket === "assumptions") {
        const a = overrides.assumptions ?? {};
        for (const f of FIELDS.assumptions) {
          if (f.name in a) {
            rows.push({ bucket, id: 0, field: f, value: (a as Record<string, unknown>)[f.name] });
          }
        }
      } else {
        const bucketMap = (overrides[bucket] ?? {}) as Record<string, unknown>;
        for (const [idStr, patch] of Object.entries(bucketMap)) {
          if (idStr === "_added") continue; // handled separately below
          if (!patch || typeof patch !== "object") continue;
          for (const f of FIELDS[bucket]) {
            if (f.name in (patch as Record<string, unknown>)) {
              rows.push({ bucket, id: Number(idStr), field: f, value: (patch as Record<string, unknown>)[f.name] });
            }
          }
        }
      }
    }
    return rows;
  }, [overrides]);

  const setOverride = (bucket: Bucket, id: number, fieldName: string, value: unknown) => {
    setDirty(true);
    setOverrides((prev) => {
      const next = { ...prev };
      if (bucket === "assumptions") {
        const a = { ...(next.assumptions ?? {}) } as Record<string, unknown>;
        if (value === null) delete a[fieldName];
        else a[fieldName] = value;
        next.assumptions = a as ScenarioOverrides["assumptions"];
        return next;
      }
      const bucketMap = { ...((next[bucket] as Record<string, Record<string, unknown>>) ?? {}) };
      const patch = { ...(bucketMap[String(id)] ?? {}) };
      if (value === null) delete patch[fieldName];
      else patch[fieldName] = value;
      if (Object.keys(patch).length === 0) delete bucketMap[String(id)];
      else bucketMap[String(id)] = patch;
      (next as Record<string, unknown>)[bucket] = bucketMap;
      return next;
    });
  };

  const removeOverride = (bucket: Bucket, id: number, fieldName: string) =>
    setOverride(bucket, id, fieldName, null);

  const addIncomeAdded = (payload: AddedIncome) => {
    setDirty(true);
    setOverrides((prev) => {
      const next = { ...prev };
      const bucket = { ...((next.incomes ?? {}) as Record<string, unknown>) };
      const list = Array.isArray(bucket._added) ? [...(bucket._added as unknown[])] : [];
      list.push(payload);
      bucket._added = list;
      next.incomes = bucket as ScenarioOverrides["incomes"];
      return next;
    });
  };

  const addExpenseAdded = (payload: AddedExpense) => {
    setDirty(true);
    setOverrides((prev) => {
      const next = { ...prev };
      const bucket = { ...((next.expenses ?? {}) as Record<string, unknown>) };
      const list = Array.isArray(bucket._added) ? [...(bucket._added as unknown[])] : [];
      list.push(payload);
      bucket._added = list;
      next.expenses = bucket as ScenarioOverrides["expenses"];
      return next;
    });
  };

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <input
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setDirty(true);
          }}
          style={{ fontSize: 18, fontWeight: 600, padding: 4, border: "1px solid transparent", borderRadius: 4, flex: 1 }}
        />
        <div className="row" style={{ gap: 6 }}>
          <button
            className="btn"
            disabled={!dirty}
            onClick={async () => {
              await onSave(overrides, name);
              setDirty(false);
            }}
          >
            {dirty ? "Save changes" : "Saved"}
          </button>
          <button className="btn btn-secondary" onClick={onDelete}>
            Delete
          </button>
        </div>
      </div>

      <ModeTabs mode={mode} setMode={setMode} overrideCount={overrideRows.length}
        addedCount={
          ((overrides.incomes?._added as unknown[] | undefined)?.length ?? 0) +
          ((overrides.expenses?._added as unknown[] | undefined)?.length ?? 0)
        }
      />

      {mode === "override" && (
        <>
      <h4 style={{ marginBottom: 8 }}>Active overrides ({overrideRows.length})</h4>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        Change one field on an existing entity (e.g. retire at 60 instead of 66; bump inflation to 4%).
      </p>
      {overrideRows.length === 0 && (
        <p className="muted">No overrides yet. Add one below to diverge from the base plan.</p>
      )}
      {overrideRows.length > 0 && (
        <ResponsiveTable
          rows={overrideRows}
          getKey={(r) => `${r.bucket}-${r.id}-${r.field.name}`}
          cardTitle={(r) => {
            const inst = instancesFor(r.bucket).find((i) => i.id === r.id);
            return `${BUCKET_LABELS[r.bucket]} · ${inst?.label ?? "?"} · ${r.field.label}`;
          }}
          columns={[
            {
              header: "Bucket",
              cell: (r) => <span className="muted">{BUCKET_LABELS[r.bucket]}</span>,
              hideOnMobile: true,
            },
            {
              header: "Target",
              cell: (r) => instancesFor(r.bucket).find((i) => i.id === r.id)?.label ?? "?",
              hideOnMobile: true,
            },
            {
              header: "Field",
              cell: (r) => r.field.label,
              hideOnMobile: true,
            },
            {
              header: "Base value",
              cell: (r) => (
                <span className="muted">
                  {formatValue(r.field, baseValueFor(r.bucket, r.id, r.field.name))}
                </span>
              ),
            },
            {
              header: "Override value",
              cell: (r) => (
                <OverrideInput
                  field={r.field}
                  value={r.value}
                  onChange={(v) => setOverride(r.bucket, r.id, r.field.name, v)}
                />
              ),
            },
          ]}
          renderActions={(r) => (
            <button
              className="btn btn-secondary"
              onClick={() => removeOverride(r.bucket, r.id, r.field.name)}
            >
              Remove
            </button>
          )}
        />
      )}

      <AddOverrideRow onAdd={(b, id, f) => setOverride(b, id, f, baseValueFor(b, id, f))} instancesFor={instancesFor} />
        </>
      )}

      {mode === "step" && (
        <StepChangeWizard
          baseYear={baseYear}
          incomes={incomes}
          expenses={expenses ?? []}
          people={people ?? []}
          onApply={(bucket, id, endYear) =>
            setOverride(bucket, id, "end_year", endYear)
          }
          onAddIncome={addIncomeAdded}
          onAddExpense={addExpenseAdded}
        />
      )}

      {mode === "added" && (
      <AddedItemsSection
        overrides={overrides}
        people={people ?? []}
        onAddIncome={addIncomeAdded}
        onRemoveAddedIncome={(idx) => {
          setDirty(true);
          setOverrides((prev) => {
            const next = { ...prev };
            const bucket = { ...((next.incomes ?? {}) as Record<string, unknown>) };
            const list = Array.isArray(bucket._added) ? [...(bucket._added as unknown[])] : [];
            list.splice(idx, 1);
            if (list.length === 0) delete bucket._added;
            else bucket._added = list;
            next.incomes = bucket as ScenarioOverrides["incomes"];
            return next;
          });
        }}
        onAddExpense={addExpenseAdded}
        onRemoveAddedExpense={(idx) => {
          setDirty(true);
          setOverrides((prev) => {
            const next = { ...prev };
            const bucket = { ...((next.expenses ?? {}) as Record<string, unknown>) };
            const list = Array.isArray(bucket._added) ? [...(bucket._added as unknown[])] : [];
            list.splice(idx, 1);
            if (list.length === 0) delete bucket._added;
            else bucket._added = list;
            next.expenses = bucket as ScenarioOverrides["expenses"];
            return next;
          });
        }}
      />

      )}

      <p style={{ marginTop: 12 }}>
        <button className="btn btn-secondary" onClick={() => setShowJson((s) => !s)}>
          {showJson ? "Hide" : "Show"} raw JSON
        </button>
      </p>
      {showJson && (
        <pre
          style={{
            background: "#0f172a",
            color: "#f8fafc",
            padding: 12,
            borderRadius: 6,
            fontSize: 12,
            overflow: "auto",
          }}
        >
          {JSON.stringify(overrides, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ModeTabs({
  mode,
  setMode,
  overrideCount,
  addedCount,
}: {
  mode: "override" | "step" | "added";
  setMode: (m: "override" | "step" | "added") => void;
  overrideCount: number;
  addedCount: number;
}) {
  const tabs: { id: "override" | "step" | "added"; label: string; sub: string; count?: number }[] = [
    { id: "override", label: "Override a field", sub: "Change a value on something in your base plan", count: overrideCount },
    { id: "step", label: "Schedule a step change", sub: "End one income/expense, start another at year Y" },
    { id: "added", label: "Add new income / expense", sub: "Promotion, wedding, inheritance — not in base plan", count: addedCount },
  ];
  return (
    <div className="row" style={{ gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
      {tabs.map((t) => {
        const selected = mode === t.id;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => setMode(t.id)}
            style={{
              flex: 1,
              minWidth: 200,
              textAlign: "left",
              padding: "8px 12px",
              borderRadius: 6,
              border: selected ? "2px solid #2563eb" : "1px solid #cbd5e1",
              background: selected ? "#eff6ff" : "#fff",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            <div style={{ fontWeight: 600 }}>
              {t.label}
              {typeof t.count === "number" && t.count > 0 && (
                <span
                  style={{
                    marginLeft: 6,
                    background: "#2563eb",
                    color: "#fff",
                    borderRadius: 999,
                    padding: "1px 6px",
                    fontSize: 11,
                  }}
                >
                  {t.count}
                </span>
              )}
            </div>
            <div className="muted" style={{ fontSize: 11, lineHeight: 1.3 }}>{t.sub}</div>
          </button>
        );
      })}
    </div>
  );
}

function OverrideInput({
  field,
  value,
  onChange,
}: {
  field: FieldDef;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (field.kind === "percent") {
    return (
      <input
        type="number"
        step="0.001"
        value={value === null || value === undefined ? "" : Number(value)}
        onChange={(e) => onChange(parseValue(field, e.target.value))}
        style={{ padding: "4px 8px", border: "1px solid #cbd5e1", borderRadius: 4, width: 100 }}
      />
    );
  }
  return (
    <input
      type={field.kind === "text" ? "text" : "number"}
      value={value === null || value === undefined ? "" : String(value)}
      onChange={(e) => onChange(parseValue(field, e.target.value))}
      style={{ padding: "4px 8px", border: "1px solid #cbd5e1", borderRadius: 4, width: 140 }}
    />
  );
}

function AddOverrideRow({
  onAdd,
  instancesFor,
}: {
  onAdd: (bucket: Bucket, id: number, fieldName: string) => void;
  instancesFor: (bucket: Bucket) => { id: number; label: string }[];
}) {
  const [bucket, setBucket] = useState<Bucket>("people");
  const insts = instancesFor(bucket);
  const [instId, setInstId] = useState<number | null>(insts[0]?.id ?? null);
  const fields = FIELDS[bucket];
  const [fieldName, setFieldName] = useState<string>(fields[0]?.name ?? "");

  useEffect(() => {
    const next = instancesFor(bucket);
    setInstId(next[0]?.id ?? null);
    setFieldName(FIELDS[bucket][0]?.name ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bucket]);

  const canAdd = instId !== null && fieldName !== "";

  return (
    <div
      className="row"
      style={{
        marginTop: 16,
        padding: 12,
        background: "#f8fafc",
        borderRadius: 6,
        border: "1px solid #e2e8f0",
        flexWrap: "wrap",
      }}
    >
      <div className="field" style={{ marginBottom: 0 }}>
        <label>Bucket</label>
        <select value={bucket} onChange={(e) => setBucket(e.target.value as Bucket)}>
          {(Object.keys(FIELDS) as Bucket[]).map((b) => (
            <option key={b} value={b}>
              {BUCKET_LABELS[b]}
            </option>
          ))}
        </select>
      </div>
      {bucket !== "assumptions" && (
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Target</label>
          <select
            value={instId ?? ""}
            onChange={(e) => setInstId(e.target.value === "" ? null : Number(e.target.value))}
          >
            {insts.map((i) => (
              <option key={i.id} value={i.id}>
                {i.label}
              </option>
            ))}
            {insts.length === 0 && <option value="">(none)</option>}
          </select>
        </div>
      )}
      <div className="field" style={{ marginBottom: 0 }}>
        <label>Field</label>
        <select value={fieldName} onChange={(e) => setFieldName(e.target.value)}>
          {fields.map((f) => (
            <option key={f.name} value={f.name}>
              {f.label}
            </option>
          ))}
        </select>
      </div>
      <button
        className="btn"
        disabled={!canAdd}
        onClick={() => {
          if (instId === null && bucket !== "assumptions") return;
          onAdd(bucket, instId ?? 0, fieldName);
        }}
        style={{ alignSelf: "flex-end" }}
      >
        Add override
      </button>
    </div>
  );
}

function StepChangeWizard({
  baseYear,
  incomes,
  expenses,
  people,
  onApply,
  onAddIncome,
  onAddExpense,
}: {
  baseYear: number;
  incomes: IncomeSource[];
  expenses: Expense[];
  people: Person[];
  onApply: (bucket: "incomes" | "expenses", id: number, endYear: number) => void;
  onAddIncome: (payload: AddedIncome) => void;
  onAddExpense: (payload: AddedExpense) => void;
}) {
  const [bucket, setBucket] = useState<"incomes" | "expenses">("incomes");
  const [instId, setInstId] = useState<number | "">("");
  const [year, setYear] = useState<number>(baseYear + 5);
  const [newValue, setNewValue] = useState<number>(0);

  const incomeOptions = incomes.map((i) => ({
    id: i.id,
    label: `${i.name} (${people.find((p) => p.id === i.person_id)?.name ?? "?"}) — €${i.gross_amount.toLocaleString()}`,
  }));
  const expenseOptions = expenses.map((e) => ({
    id: e.id,
    label: `${e.name} — €${e.amount.toLocaleString()}/yr`,
  }));
  const options = bucket === "incomes" ? incomeOptions : expenseOptions;

  const apply = () => {
    if (instId === "") return;
    const id = Number(instId);
    onApply(bucket, id, year - 1);

    if (bucket === "incomes") {
      const orig = incomes.find((i) => i.id === id);
      if (!orig) return;
      onAddIncome({
        person_id: orig.person_id,
        kind: orig.kind,
        name: `${orig.name} (from ${year})`,
        gross_amount: newValue,
        start_year: year,
        end_year: orig.end_year ?? null,
        escalation_rate: orig.escalation_rate,
        pays_prsi: orig.pays_prsi,
        pays_usc: orig.pays_usc,
        pension_contribution_pct: orig.pension_contribution_pct,
        employer_pension_contribution_pct: orig.employer_pension_contribution_pct,
      });
    } else {
      const orig = expenses.find((e) => e.id === id);
      if (!orig) return;
      onAddExpense({
        name: `${orig.name} (from ${year})`,
        category: orig.category,
        amount: newValue,
        start_year: year,
        end_year: orig.end_year ?? null,
        escalation_rate: orig.escalation_rate,
        owner_person_id: orig.owner_person_id,
      });
    }

    setInstId("");
    setNewValue(0);
  };

  const canApply =
    instId !== "" && Number.isFinite(year) && year > baseYear && Number.isFinite(newValue);

  return (
    <div style={{ marginTop: 24 }}>
      <h4 style={{ marginBottom: 8 }}>
        Schedule a step change
        <HelpTip>
          Models an event in year Y that changes a recurring income or expense to a new value.
          Behind the scenes this ends the original entry at year Y−1 and adds a replacement
          starting at year Y. Use this for promotions, salary cuts, mortgage drop-offs, etc.
        </HelpTip>
      </h4>
      <div
        className="row"
        style={{
          padding: 12,
          background: "#f0f9ff",
          borderRadius: 6,
          border: "1px solid #bae6fd",
          flexWrap: "wrap",
          alignItems: "flex-end",
        }}
      >
        <div className="field" style={{ marginBottom: 0 }}>
          <label>What changes</label>
          <select
            value={bucket}
            onChange={(e) => {
              setBucket(e.target.value as "incomes" | "expenses");
              setInstId("");
            }}
          >
            <option value="incomes">Income</option>
            <option value="expenses">Expense</option>
          </select>
        </div>
        <div className="field" style={{ marginBottom: 0, flex: 2, minWidth: 220 }}>
          <label>Target</label>
          <select
            value={instId}
            onChange={(e) => setInstId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">— pick one —</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ marginBottom: 0, minWidth: 110 }}>
          <label>New value (€/yr)</label>
          <NumericInput
            value={newValue}
            onChange={(v) => Number.isFinite(v) && setNewValue(v)}
          />
        </div>
        <div className="field" style={{ marginBottom: 0, minWidth: 100 }}>
          <label>Starting year</label>
          <NumericInput
            integer
            value={year}
            onChange={(v) => Number.isFinite(v) && setYear(v)}
          />
        </div>
        <button className="btn" disabled={!canApply} onClick={apply}>
          Apply
        </button>
      </div>
    </div>
  );
}

function AddedItemsSection({
  overrides,
  people,
  onAddIncome,
  onRemoveAddedIncome,
  onAddExpense,
  onRemoveAddedExpense,
}: {
  overrides: ScenarioOverrides;
  people: Person[];
  onAddIncome: (payload: AddedIncome) => void;
  onRemoveAddedIncome: (idx: number) => void;
  onAddExpense: (payload: AddedExpense) => void;
  onRemoveAddedExpense: (idx: number) => void;
}) {
  const addedIncomes = (overrides.incomes?._added ?? []) as AddedIncome[];
  const addedExpenses = (overrides.expenses?._added ?? []) as AddedExpense[];
  const [showAddIncome, setShowAddIncome] = useState(false);
  const [showAddExpense, setShowAddExpense] = useState(false);

  return (
    <div style={{ marginTop: 24 }}>
      <h4 style={{ marginBottom: 8 }}>
        New entities added by this scenario
        <HelpTip>
          Use this to model events that don't exist in the base plan: a promotion (extra
          income source from year X), a one-off cost like a wedding, an inheritance, or an
          additional ongoing expense. The base plan stays untouched.
        </HelpTip>
      </h4>

      <div className="row" style={{ gap: 8, marginBottom: 8 }}>
        <button className="btn btn-secondary" onClick={() => setShowAddIncome((s) => !s)}>
          {showAddIncome ? "Cancel" : "+ Add income (e.g. promotion)"}
        </button>
        <button className="btn btn-secondary" onClick={() => setShowAddExpense((s) => !s)}>
          {showAddExpense ? "Cancel" : "+ Add expense (one-off or recurring)"}
        </button>
      </div>

      {showAddIncome && (
        <AddIncomeForm
          people={people}
          onSubmit={(payload) => {
            onAddIncome(payload);
            setShowAddIncome(false);
          }}
        />
      )}
      {showAddExpense && (
        <AddExpenseForm
          onSubmit={(payload) => {
            onAddExpense(payload);
            setShowAddExpense(false);
          }}
        />
      )}

      {(addedIncomes.length > 0 || addedExpenses.length > 0) && (
        <div style={{ marginTop: 8 }}>
          <ResponsiveTable<
            | { kind: "income"; idx: number; row: AddedIncome }
            | { kind: "expense"; idx: number; row: AddedExpense }
          >
            rows={[
              ...addedIncomes.map((row, idx) => ({ kind: "income" as const, idx, row })),
              ...addedExpenses.map((row, idx) => ({ kind: "expense" as const, idx, row })),
            ]}
            getKey={(r) => `${r.kind}-${r.idx}`}
            cardTitle={(r) => r.row.name}
            columns={[
              {
                header: "Type",
                cell: (r) => (
                  <span className="muted">{r.kind === "income" ? "Income" : "Expense"}</span>
                ),
              },
              { header: "Name", cell: (r) => r.row.name, hideOnMobile: true },
              {
                header: "Amount / year",
                cell: (r) =>
                  r.kind === "income"
                    ? `€${Number(r.row.gross_amount).toLocaleString()}`
                    : `€${Number(r.row.amount).toLocaleString()}`,
              },
              {
                header: "Years",
                cell: (r) =>
                  r.kind === "income"
                    ? `${r.row.start_year}${r.row.end_year ? `–${r.row.end_year}` : "+"}`
                    : `${r.row.start_year}${
                        r.row.category === "single_year"
                          ? " (one-off)"
                          : r.row.end_year
                          ? `–${r.row.end_year}`
                          : "+"
                      }`,
              },
              {
                header: "Detail",
                cell: (r) => (
                  <span className="muted">
                    {r.kind === "income"
                      ? `${r.row.kind} · ${
                          people.find((p) => p.id === r.row.person_id)?.name ??
                          `person ${r.row.person_id}`
                        }`
                      : r.row.category}
                  </span>
                ),
              },
            ]}
            renderActions={(r) => (
              <button
                className="btn btn-secondary"
                onClick={() =>
                  r.kind === "income"
                    ? onRemoveAddedIncome(r.idx)
                    : onRemoveAddedExpense(r.idx)
                }
              >
                Remove
              </button>
            )}
          />
        </div>
      )}
    </div>
  );
}

const INCOME_KINDS: { value: IncomeKind; label: string }[] = [
  { value: "employment", label: "Employment / promotion" },
  { value: "self_employment", label: "Self-employment" },
  { value: "rental", label: "Rental" },
  { value: "other", label: "Other" },
];

function AddIncomeForm({
  people,
  onSubmit,
}: {
  people: Person[];
  onSubmit: (payload: AddedIncome) => void;
}) {
  const [personId, setPersonId] = useState<number | null>(people[0]?.id ?? null);
  const [name, setName] = useState("Promotion bump");
  const [kind, setKind] = useState<IncomeKind>("employment");
  const [grossAmount, setGrossAmount] = useState(20_000);
  const [startYear, setStartYear] = useState(new Date().getFullYear() + 1);
  const [endYear, setEndYear] = useState<number | "">("");
  const [escalation, setEscalation] = useState(0.03);

  if (personId === null) {
    return (
      <p className="muted" style={{ padding: 12 }}>
        Add a person to the base plan first before adding scenario income.
      </p>
    );
  }

  return (
    <div className="card" style={{ background: "#f8fafc" }}>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <div className="field">
          <label>Person</label>
          <select value={personId} onChange={(e) => setPersonId(Number(e.target.value))}>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Kind</label>
          <select value={kind} onChange={(e) => setKind(e.target.value as IncomeKind)}>
            {INCOME_KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 180 }}>
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label>
            Gross / year
            <HelpTip>
              For a promotion, enter the <em>delta</em> over your base salary (e.g. 20,000 if your
              salary jumps from 80k to 100k). The base income source keeps running unchanged.
            </HelpTip>
          </label>
          <input
            type="number"
            value={grossAmount}
            onChange={(e) => setGrossAmount(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>Start year</label>
          <input
            type="number"
            value={startYear}
            onChange={(e) => setStartYear(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>End year (optional)</label>
          <input
            type="number"
            value={endYear}
            onChange={(e) => setEndYear(e.target.value === "" ? "" : Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>Escalation %</label>
          <input
            type="number"
            step="0.5"
            value={escalation * 100}
            onChange={(e) => setEscalation(Number(e.target.value) / 100)}
          />
        </div>
      </div>
      <button
        className="btn"
        onClick={() =>
          onSubmit({
            person_id: personId,
            kind,
            name,
            gross_amount: grossAmount,
            start_year: startYear,
            end_year: endYear === "" ? null : endYear,
            escalation_rate: escalation,
          })
        }
      >
        Add to scenario
      </button>
    </div>
  );
}

const EXPENSE_CATEGORIES: { value: ExpenseCategory; label: string; help: string }[] = [
  { value: "single_year", label: "One-off (single year)", help: "Fires once in start year only — wedding, car, big trip." },
  { value: "basic", label: "Basic (recurring)", help: "Recurring essential expense from start year to end year (or forever)." },
  { value: "discretionary", label: "Discretionary (recurring)", help: "Recurring optional spend." },
  { value: "legacy", label: "Legacy / inheritance plan", help: "Recurring legacy provision." },
];

function AddExpenseForm({ onSubmit }: { onSubmit: (payload: AddedExpense) => void }) {
  const [name, setName] = useState("Wedding");
  const [category, setCategory] = useState<ExpenseCategory>("single_year");
  const [amount, setAmount] = useState(20_000);
  const [startYear, setStartYear] = useState(new Date().getFullYear() + 1);
  const [endYear, setEndYear] = useState<number | "">("");
  const [escalation, setEscalation] = useState(0.025);

  const meta = EXPENSE_CATEGORIES.find((c) => c.value === category);

  return (
    <div className="card" style={{ background: "#f8fafc" }}>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <div className="field" style={{ flex: 1, minWidth: 180 }}>
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label>
            Category
            {meta && <HelpTip>{meta.help}</HelpTip>}
          </label>
          <select value={category} onChange={(e) => setCategory(e.target.value as ExpenseCategory)}>
            {EXPENSE_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Amount</label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
          />
        </div>
        <div className="field">
          <label>Start year</label>
          <input
            type="number"
            value={startYear}
            onChange={(e) => setStartYear(Number(e.target.value))}
          />
        </div>
        {category !== "single_year" && (
          <>
            <div className="field">
              <label>End year (optional)</label>
              <input
                type="number"
                value={endYear}
                onChange={(e) => setEndYear(e.target.value === "" ? "" : Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>Escalation %</label>
              <input
                type="number"
                step="0.5"
                value={escalation * 100}
                onChange={(e) => setEscalation(Number(e.target.value) / 100)}
              />
            </div>
          </>
        )}
      </div>
      <button
        className="btn"
        onClick={() =>
          onSubmit({
            name,
            category,
            amount,
            start_year: startYear,
            end_year: category === "single_year" ? null : endYear === "" ? null : endYear,
            escalation_rate: category === "single_year" ? 0 : escalation,
          })
        }
      >
        Add to scenario
      </button>
    </div>
  );
}
