import { useEffect, useState } from "react";

import {
  useAssets,
  useCreateAsset,
  useDeleteAsset,
  useLiabilities,
  usePeople,
  useUpdateAsset,
} from "../../api/hooks";
import type { Asset, AssetKind, Liability } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { EmptyState } from "../../components/EmptyState";
import { JargonTerm } from "../../components/JargonTerm";
import { NumericInput } from "../../components/NumericInput";
import { ResponsiveTable } from "../../components/ResponsiveTable";
import { EditModal } from "../../components/EditModal";
import { useToast } from "../../components/Toast";
import { fmtMoney, fmtPctDisplay } from "../../lib/format";

const PENSION_KINDS: AssetKind[] = ["prsa", "occupational_pension", "arf"];
const AVC_KINDS: AssetKind[] = ["prsa", "occupational_pension"];  // ARF excluded — no new contributions
const NO_CONTRIB_KINDS: AssetKind[] = ["arf"];  // post-retirement drawdown only

const KIND_GROUPS: { label: string; kinds: AssetKind[] }[] = [
  { label: "Cash & deposits", kinds: ["cash", "deposit"] },
  { label: "Investments", kinds: ["investment_unwrapped", "etf_fund"] },
  { label: "Pensions", kinds: ["prsa", "occupational_pension", "arf"] },
  { label: "Property", kinds: ["property_primary", "property_btl"] },
];

const KINDS: { value: AssetKind; label: string; defaultGrowth: number; help?: string }[] = [
  { value: "cash", label: "Cash / current account", defaultGrowth: 0.0 },
  {
    value: "deposit",
    label: "Deposit account (DIRT)",
    defaultGrowth: 0.025,
    help: "Bank deposit. Interest is taxed at 33% Deposit Interest Retention Tax (DIRT).",
  },
  {
    value: "investment_unwrapped",
    label: "Investment (unwrapped, CGT)",
    defaultGrowth: 0.05,
    help: "Direct shares or non-fund securities held outside any tax wrapper. Gains on sale are taxed at 33% CGT (with €1,270 annual exemption).",
  },
  {
    value: "etf_fund",
    label: "ETF / fund (41% exit tax)",
    defaultGrowth: 0.05,
    help: "Irish/EU UCITS ETFs and unit-linked funds. Gains taxed at 41% exit tax, with deemed disposal every 8 years even if not sold.",
  },
  {
    value: "prsa",
    label: "PRSA pension",
    defaultGrowth: 0.05,
    help: "Personal Retirement Savings Account. Tax-relievable contributions, tax-free growth, taxed on drawdown.",
  },
  {
    value: "occupational_pension",
    label: "Occupational pension",
    defaultGrowth: 0.05,
    help: "Employer-sponsored DC scheme. Same tax treatment as PRSA from the saver's perspective.",
  },
  {
    value: "arf",
    label: "ARF (post-retirement)",
    defaultGrowth: 0.04,
    help: "Approved Retirement Fund. Receives 75% of the pension pot at retirement. Subject to imputed minimum drawdown (4% age 60-69, 5% from 70).",
  },
  { value: "property_primary", label: "Property (primary residence)", defaultGrowth: 0.03 },
  { value: "property_btl", label: "Property (buy-to-let)", defaultGrowth: 0.03 },
];

type ContribMode = "none" | "fixed" | "pct_net" | "pct_gross";
type AvcMode = "none" | "fixed" | "pct_gross";

type FormState = {
  name: string;
  kind: AssetKind;
  value: number;
  growth_rate: number;
  cost_basis: number;
  owner_person_id: number | null;
  acquired_year: number | "";
  contrib_mode: ContribMode;
  annual_contribution: number;
  contribution_pct: number;
  contribution_start_year: number | "";
  contribution_end_year: number | "";
  avc_mode: AvcMode;
  avc_value: number;
  purchase_year: number | "";
  deposit: number;
  disposal_year: number | "";
  linked_liability_id: number | null;
  stamp_duty_pct: number;
  selling_cost_pct: number;
};

const blankForm: FormState = {
  name: "Current account",
  kind: "cash",
  value: 10000,
  growth_rate: 0.0,
  cost_basis: 0,
  owner_person_id: null,
  acquired_year: "",
  contrib_mode: "none",
  annual_contribution: 0,
  contribution_pct: 0,
  contribution_start_year: "",
  contribution_end_year: "",
  avc_mode: "none",
  avc_value: 0,
  purchase_year: "",
  deposit: 0,
  disposal_year: "",
  linked_liability_id: null,
  stamp_duty_pct: 0,
  selling_cost_pct: 0,
};

function inferContribMode(a: Asset): ContribMode {
  if (a.contribution_pct_of_gross_income > 0) return "pct_gross";
  if (a.contribution_pct_of_net_income > 0) return "pct_net";
  if (a.annual_contribution > 0) return "fixed";
  return "none";
}

function inferAvcMode(a: Asset): AvcMode {
  if (a.avc_pct_of_gross > 0) return "pct_gross";
  if (a.avc_annual > 0) return "fixed";
  return "none";
}

function fromAsset(a: Asset): FormState {
  const mode = inferContribMode(a);
  const avcMode = inferAvcMode(a);
  return {
    name: a.name,
    kind: a.kind,
    value: a.value,
    growth_rate: a.growth_rate,
    cost_basis: a.cost_basis,
    owner_person_id: a.owner_person_id,
    acquired_year: a.acquired_year ?? "",
    contrib_mode: mode,
    annual_contribution: a.annual_contribution,
    contribution_pct:
      mode === "pct_gross"
        ? a.contribution_pct_of_gross_income
        : a.contribution_pct_of_net_income,
    contribution_start_year: a.contribution_start_year ?? "",
    contribution_end_year: a.contribution_end_year ?? "",
    avc_mode: avcMode,
    avc_value: avcMode === "pct_gross" ? a.avc_pct_of_gross : a.avc_annual,
    purchase_year: a.purchase_year ?? "",
    deposit: a.deposit ?? 0,
    disposal_year: a.disposal_year ?? "",
    linked_liability_id: a.linked_liability_id ?? null,
    stamp_duty_pct: a.stamp_duty_pct ?? 0,
    selling_cost_pct: a.selling_cost_pct ?? 0,
  };
}

export function AssetsPane({ planId }: { planId: number }) {
  const { data, isLoading } = useAssets(planId);
  const { data: people } = usePeople(planId);
  const { data: liabilities } = useLiabilities(planId);
  const create = useCreateAsset(planId);
  const update = useUpdateAsset(planId);
  const del = useDeleteAsset(planId);

  const [form, setForm] = useState<FormState>(blankForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(blankForm);
  const toast = useToast();

  const softDeleteAsset = (a: Asset) => {
    del.mutate(a.id);
    toast.push({
      kind: "info",
      message: `Deleted "${a.name}".`,
      autoDismissMs: 8000,
      action: {
        label: "Undo",
        onClick: () => {
          create.mutate({
            name: a.name,
            kind: a.kind,
            value: a.value,
            growth_rate: a.growth_rate,
            cost_basis: a.cost_basis,
            owner_person_id: a.owner_person_id,
            acquired_year: a.acquired_year,
            annual_contribution: a.annual_contribution,
            contribution_pct_of_net_income: a.contribution_pct_of_net_income,
            contribution_pct_of_gross_income: a.contribution_pct_of_gross_income,
            contribution_start_year: a.contribution_start_year,
            contribution_end_year: a.contribution_end_year,
            avc_annual: a.avc_annual,
            avc_pct_of_gross: a.avc_pct_of_gross,
            purchase_year: a.purchase_year,
            deposit: a.deposit,
            disposal_year: a.disposal_year,
            linked_liability_id: a.linked_liability_id,
            stamp_duty_pct: a.stamp_duty_pct,
            selling_cost_pct: a.selling_cost_pct,
          });
        },
      },
    });
  };

  useEffect(() => {
    if (editingId === null || !data) return;
    const row = data.find((d) => d.id === editingId);
    if (row) setEditForm(fromAsset(row));
  }, [editingId, data]);

  const onKindChange = (kind: AssetKind, target: FormState, setter: (f: FormState) => void) => {
    const meta = KINDS.find((k) => k.value === kind)!;
    setter({ ...target, kind, growth_rate: meta.defaultGrowth });
  };

  const buildPayload = (f: FormState) => ({
    name: f.name.trim(),
    kind: f.kind,
    value: f.value,
    growth_rate: f.growth_rate,
    cost_basis: f.cost_basis,
    owner_person_id: f.owner_person_id,
    acquired_year: f.acquired_year === "" ? null : f.acquired_year,
    // Pension assets use AVC fields; all others use regular contribution fields.
    annual_contribution: AVC_KINDS.includes(f.kind) ? 0 : (f.contrib_mode === "fixed" ? f.annual_contribution : 0),
    contribution_pct_of_net_income: AVC_KINDS.includes(f.kind) ? 0 : (f.contrib_mode === "pct_net" ? f.contribution_pct : 0),
    contribution_pct_of_gross_income: AVC_KINDS.includes(f.kind) ? 0 : (f.contrib_mode === "pct_gross" ? f.contribution_pct : 0),
    contribution_start_year:
      (AVC_KINDS.includes(f.kind) || f.contrib_mode === "none") ? null :
      f.contribution_start_year === "" ? null : f.contribution_start_year,
    contribution_end_year:
      (AVC_KINDS.includes(f.kind) || f.contrib_mode === "none") ? null :
      f.contribution_end_year === "" ? null : f.contribution_end_year,
    avc_annual: f.avc_mode === "fixed" ? f.avc_value : 0,
    avc_pct_of_gross: f.avc_mode === "pct_gross" ? f.avc_value : 0,
    purchase_year: f.purchase_year === "" ? null : f.purchase_year,
    deposit: f.purchase_year === "" ? 0 : Math.max(0, f.deposit),
    disposal_year: f.disposal_year === "" ? null : f.disposal_year,
    // Link/cost only meaningful for a property with a planned sale.
    linked_liability_id: f.disposal_year === "" ? null : f.linked_liability_id,
    stamp_duty_pct: f.purchase_year === "" ? 0 : Math.max(0, f.stamp_duty_pct),
    selling_cost_pct: f.disposal_year === "" ? 0 : Math.max(0, f.selling_cost_pct),
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

  const ownerRequired = PENSION_KINDS.includes(form.kind);

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add asset</h3>
        <form onSubmit={onSubmit}>
          <FormFields
            form={form}
            setForm={setForm}
            onKindChange={(k) => onKindChange(k, form, setForm)}
            people={people ?? []}
            liabilities={liabilities ?? []}
          />
          <button
            type="submit"
            className="btn"
            disabled={create.isPending || (ownerRequired && form.owner_person_id === null)}
          >
            Add
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Assets</h3>
        {isLoading && <p className="muted">Loading…</p>}
        {data && data.length === 0 && (
          <EmptyState
            title="Add what you own."
            hint={
              <>
                Cash, pensions, your home, ETFs — anything that grows or generates income. Each
                asset's tax treatment is built in (e.g. ETFs use{" "}
                <JargonTerm term="ETF_EXIT_TAX">41% exit tax</JargonTerm>, properties use{" "}
                <JargonTerm term="CGT" />).
              </>
            }
          />
        )}
        {data && data.length > 0 && (
          <ResponsiveTable<Asset>
            rows={data}
            getKey={(a) => a.id}
            cardTitle={(a) => a.name}
            columns={[
              { header: "Name", cell: (a) => a.name, hideOnMobile: true },
              {
                header: "Type",
                cell: (a) => (
                  <span className="muted">
                    {KINDS.find((k) => k.value === a.kind)?.label ?? a.kind}
                  </span>
                ),
              },
              { header: "Value", cell: (a) => fmtMoney(a.value) },
              { header: "Growth", cell: (a) => fmtPctDisplay(a.growth_rate) },
              {
                header: "Monthly",
                cell: (a) => (
                  <span className="muted">
                    {a.avc_pct_of_gross > 0
                      ? `AVC ${fmtPctDisplay(a.avc_pct_of_gross)} gross`
                      : a.avc_annual > 0
                      ? `AVC ${fmtMoney(a.avc_annual)}/yr`
                      : a.contribution_pct_of_gross_income > 0
                      ? `${fmtPctDisplay(a.contribution_pct_of_gross_income)} gross`
                      : a.contribution_pct_of_net_income > 0
                      ? `${fmtPctDisplay(a.contribution_pct_of_net_income)} net`
                      : a.annual_contribution > 0
                      ? `${fmtMoney(a.annual_contribution / 12)}/mo`
                      : "—"}
                  </span>
                ),
              },
              {
                header: "Owner",
                cell: (a) => (
                  <span className="muted">
                    {a.owner_person_id
                      ? people?.find((p) => p.id === a.owner_person_id)?.name ?? "—"
                      : "Joint"}
                  </span>
                ),
              },
            ]}
            renderActions={(a) => (
              <>
                <button
                  className="btn btn-secondary"
                  style={{ marginRight: 6 }}
                  onClick={() => setEditingId(a.id)}
                >
                  Edit
                </button>
                <button className="btn btn-secondary" onClick={() => softDeleteAsset(a)}>
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
        title="Edit asset"
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
        <FormFields
          form={editForm}
          setForm={setEditForm}
          onKindChange={(k) => onKindChange(k, editForm, setEditForm)}
          people={people ?? []}
          liabilities={liabilities ?? []}
        />
      </EditModal>
    </div>
  );
}

function FormFields({
  form,
  setForm,
  onKindChange,
  people,
  liabilities,
}: {
  form: FormState;
  setForm: (f: FormState) => void;
  onKindChange: (kind: AssetKind) => void;
  people: { id: number; name: string }[];
  liabilities: Liability[];
}) {
  const meta = KINDS.find((k) => k.value === form.kind);
  const ownerRequired = PENSION_KINDS.includes(form.kind);
  return (
    <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
      <div className="field" style={{ flex: 2, minWidth: 200 }}>
        <label>
          Type
          {meta?.help && <HelpTip>{meta.help}</HelpTip>}
        </label>
        <select
          value={form.kind}
          onChange={(e) => onKindChange(e.target.value as AssetKind)}
        >
          {KIND_GROUPS.map((g) => (
            <optgroup key={g.label} label={g.label}>
              {g.kinds.map((kv) => {
                const k = KINDS.find((x) => x.value === kv);
                if (!k) return null;
                return (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                );
              })}
            </optgroup>
          ))}
        </select>
      </div>
      <div className="field" style={{ flex: 2, minWidth: 180 }}>
        <label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 110 }}>
        <label>Value (€)</label>
        <NumericInput
          value={form.value}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, value: v })}
        />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 100 }}>
        <label>Growth %</label>
        <NumericInput
          value={form.growth_rate * 100}
          onChange={(v) => Number.isFinite(v) && setForm({ ...form, growth_rate: v / 100 })}
        />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 110 }}>
        <label>
          Acquired
          <HelpTip>
            Year the asset was acquired. Used by the simulator for ETF 8-year deemed-disposal
            timing and CGT cost-basis tracking. Leave blank if unknown — the simulator falls
            back to base_year for ETFs.
          </HelpTip>
        </label>
        <NumericInput
          integer
          placeholder="e.g. 2022"
          value={form.acquired_year === "" ? NaN : form.acquired_year}
          onChange={(v) => setForm({ ...form, acquired_year: Number.isFinite(v) ? v : "" })}
        />
      </div>
      <div className="field" style={{ flex: 1, minWidth: 140 }}>
        <label>Owner{ownerRequired ? " *" : ""}</label>
        <select
          value={form.owner_person_id ?? ""}
          onChange={(e) =>
            setForm({
              ...form,
              owner_person_id: e.target.value === "" ? null : Number(e.target.value),
            })
          }
        >
          <option value="">Joint / unassigned</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      {/* ARF: no contributions of any kind */}
      {NO_CONTRIB_KINDS.includes(form.kind) && (
        <p className="muted" style={{ fontSize: 12, margin: "0 0 8px", flexBasis: "100%" }}>
          <JargonTerm term="ARF" /> accepts no new contributions — it receives the pension pot at
          retirement and distributes via mandatory drawdown.
        </p>
      )}

      {/* PRSA / occupational pension: AVC fields only */}
      {AVC_KINDS.includes(form.kind) && (
        <details
          open={form.avc_mode !== "none"}
          style={{ flexBasis: "100%", marginTop: 4, borderTop: "1px dashed #e2e8f0", paddingTop: 8 }}
        >
          <summary style={{ cursor: "pointer", fontSize: 13, color: "#2563eb", userSelect: "none" }}>
            {form.avc_mode === "none" ? "+ Add AVC contributions" : "AVC contributions"}
          </summary>
          <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}>
          <div className="field" style={{ flex: 1, minWidth: 160 }}>
            <label>
              AVC
              <HelpTip>
                Additional Voluntary Contributions are pre-tax pension contributions on top of
                your salary-linked %. They get income tax relief and are jointly capped with your
                regular contribution by the age-based limit (15%–40% of earnings up to €115k).
              </HelpTip>
            </label>
            <select
              value={form.avc_mode}
              onChange={(e) => setForm({ ...form, avc_mode: e.target.value as AvcMode })}
            >
              <option value="none">None</option>
              <option value="fixed">Fixed annual amount</option>
              <option value="pct_gross">% of gross salary</option>
            </select>
          </div>
          {form.avc_mode === "fixed" && (
            <div className="field" style={{ flex: 1, minWidth: 120 }}>
              <label>Annual AVC (€)</label>
              <NumericInput
                placeholder="e.g. 2400"
                value={form.avc_value > 0 ? form.avc_value : NaN}
                onChange={(v) => setForm({ ...form, avc_value: Number.isFinite(v) ? v : 0 })}
              />
            </div>
          )}
          {form.avc_mode === "pct_gross" && (
            <div className="field" style={{ flex: 1, minWidth: 120 }}>
              <label>% of gross salary</label>
              <NumericInput
                placeholder="e.g. 5"
                value={form.avc_value > 0 ? form.avc_value * 100 : NaN}
                onChange={(v) =>
                  setForm({ ...form, avc_value: Number.isFinite(v) ? v / 100 : 0 })
                }
              />
            </div>
          )}
          </div>
        </details>
      )}

      {/* All non-pension assets: regular contributions */}
      {!AVC_KINDS.includes(form.kind) && !NO_CONTRIB_KINDS.includes(form.kind) && (
        <details
          open={form.contrib_mode !== "none"}
          style={{ flexBasis: "100%", marginTop: 4, borderTop: "1px dashed #e2e8f0", paddingTop: 8 }}
        >
          <summary style={{ cursor: "pointer", fontSize: 13, color: "#2563eb", userSelect: "none" }}>
            {form.contrib_mode === "none" ? "+ Add regular contributions" : "Regular contributions"}
          </summary>
          <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}>
          <div className="field" style={{ flex: 1, minWidth: 160 }}>
            <label>
              Regular contributions
              <HelpTip>
                Funded from your household cash flow each year. "Fixed" is a constant monthly
                amount. "% of net income" scales with the owner's post-tax income that year.
              </HelpTip>
            </label>
            <select
              value={form.contrib_mode}
              onChange={(e) =>
                setForm({ ...form, contrib_mode: e.target.value as ContribMode })
              }
            >
              <option value="none">None</option>
              <option value="fixed">Fixed monthly amount</option>
              <option value="pct_net">% of net (post-tax) income</option>
              <option value="pct_gross">% of gross (pre-tax) income</option>
            </select>
          </div>
          {form.contrib_mode === "fixed" && (
            <div className="field" style={{ flex: 1, minWidth: 120 }}>
              <label>Monthly (€)</label>
              <NumericInput
                placeholder="e.g. 100"
                value={form.annual_contribution > 0 ? form.annual_contribution / 12 : NaN}
                onChange={(v) =>
                  setForm({ ...form, annual_contribution: Number.isFinite(v) ? v * 12 : 0 })
                }
              />
            </div>
          )}
          {(form.contrib_mode === "pct_net" || form.contrib_mode === "pct_gross") && (
            <div className="field" style={{ flex: 1, minWidth: 120 }}>
              <label>
                {form.contrib_mode === "pct_gross" ? "% of gross income" : "% of net income"}
              </label>
              <NumericInput
                placeholder="e.g. 10"
                value={form.contribution_pct > 0 ? form.contribution_pct * 100 : NaN}
                onChange={(v) =>
                  setForm({ ...form, contribution_pct: Number.isFinite(v) ? v / 100 : 0 })
                }
              />
            </div>
          )}
          {form.contrib_mode !== "none" && (
            <>
              <div className="field" style={{ flex: 1, minWidth: 110 }}>
                <label>From year</label>
                <NumericInput
                  integer
                  placeholder="plan start"
                  value={form.contribution_start_year === "" ? NaN : form.contribution_start_year}
                  onChange={(v) =>
                    setForm({ ...form, contribution_start_year: Number.isFinite(v) ? v : "" })
                  }
                />
              </div>
              <div className="field" style={{ flex: 1, minWidth: 110 }}>
                <label>
                  Until year
                  <HelpTip>Leave blank to contribute indefinitely.</HelpTip>
                </label>
                <NumericInput
                  integer
                  placeholder="no end"
                  value={form.contribution_end_year === "" ? NaN : form.contribution_end_year}
                  onChange={(v) =>
                    setForm({ ...form, contribution_end_year: Number.isFinite(v) ? v : "" })
                  }
                />
              </div>
            </>
          )}
          </div>
        </details>
      )}

      {/* Planned purchase / sale (move house, buy a second home). Works for any
          asset but is built for property. */}
      {!AVC_KINDS.includes(form.kind) && !NO_CONTRIB_KINDS.includes(form.kind) && (
        <details
          open={form.purchase_year !== "" || form.disposal_year !== ""}
          style={{ flexBasis: "100%", marginTop: 4, borderTop: "1px dashed #e2e8f0", paddingTop: 8 }}
        >
          <summary style={{ cursor: "pointer", fontSize: 13, color: "#2563eb", userSelect: "none" }}>
            {form.purchase_year === "" && form.disposal_year === ""
              ? "+ Buy in future / sell later"
              : "Planned purchase / sale"}
          </summary>
          <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap", marginTop: 8 }}>
            <div className="field" style={{ flex: 1, minWidth: 120 }}>
              <label>
                Buy in year
                <HelpTip>
                  Leave blank if you already own it. Set a future year to buy it then: it holds no
                  value until that year, when its Value above appears and the deposit below leaves
                  your cash. Fund the rest by adding a mortgage (Liabilities) starting the same year.
                </HelpTip>
              </label>
              <NumericInput
                integer
                placeholder="already owned"
                value={form.purchase_year === "" ? NaN : form.purchase_year}
                onChange={(v) => setForm({ ...form, purchase_year: Number.isFinite(v) ? v : "" })}
              />
            </div>
            {form.purchase_year !== "" && (
              <>
                <div className="field" style={{ flex: 1, minWidth: 120 }}>
                  <label>
                    Deposit (€)
                    <HelpTip>
                      Cash paid from your savings on purchase. The remainder of the Value is assumed
                      financed by a mortgage you add separately.
                    </HelpTip>
                  </label>
                  <NumericInput
                    value={form.deposit}
                    onChange={(v) => Number.isFinite(v) && setForm({ ...form, deposit: Math.max(0, v) })}
                  />
                </div>
                <div className="field" style={{ flex: 1, minWidth: 120 }}>
                  <label>
                    Stamp duty %
                    <HelpTip>
                      Stamp duty paid from cash on purchase, as a % of the price. Irish residential:
                      1% up to €1m, 2% above; non-residential 7.5%. Leave 0 to skip.
                    </HelpTip>
                  </label>
                  <NumericInput
                    value={form.stamp_duty_pct * 100}
                    onChange={(v) =>
                      Number.isFinite(v) && setForm({ ...form, stamp_duty_pct: Math.max(0, v) / 100 })
                    }
                  />
                </div>
              </>
            )}
            <div className="field" style={{ flex: 1, minWidth: 120 }}>
              <label>
                Sell in year
                <HelpTip>
                  Set a year to deliberately sell the whole asset: the proceeds land in your cash
                  that year (a primary residence is CGT-exempt; a buy-to-let pays CGT on the gain;
                  ETFs/investments pay disposal tax). Selling the old home and buying a new one in
                  the same year models moving house.
                </HelpTip>
              </label>
              <NumericInput
                integer
                placeholder="never"
                value={form.disposal_year === "" ? NaN : form.disposal_year}
                onChange={(v) => setForm({ ...form, disposal_year: Number.isFinite(v) ? v : "" })}
              />
            </div>
            {form.disposal_year !== "" && (
              <>
                <div className="field" style={{ flex: 1, minWidth: 120 }}>
                  <label>
                    Selling costs %
                    <HelpTip>
                      Agent + legal fees taken off the sale proceeds, as a % of the sale price.
                    </HelpTip>
                  </label>
                  <NumericInput
                    value={form.selling_cost_pct * 100}
                    onChange={(v) =>
                      Number.isFinite(v) && setForm({ ...form, selling_cost_pct: Math.max(0, v) / 100 })
                    }
                  />
                </div>
                <div className="field" style={{ flex: 1, minWidth: 160 }}>
                  <label>
                    Clears mortgage
                    <HelpTip>
                      The mortgage this property financed. On sale its outstanding balance is repaid
                      from the proceeds and its amortisation stops.
                    </HelpTip>
                  </label>
                  <select
                    value={form.linked_liability_id ?? ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        linked_liability_id: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  >
                    <option value="">None</option>
                    {liabilities.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </div>
        </details>
      )}
    </div>
  );
}
