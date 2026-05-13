import { useEffect, useMemo, useState } from "react";

import {
  useCreateTaxConfig,
  useDeleteTaxConfig,
  usePlan,
  useTaxConfigs,
  useUpdatePlan,
  useUpdateTaxConfig,
} from "../../api/hooks";
import type { TaxConfigSummary } from "../../api/types";
import { HelpTip } from "../../components/HelpTip";
import { NumericInput } from "../../components/NumericInput";
import { ResponsiveTable } from "../../components/ResponsiveTable";

// The fields surfaced as named inputs. Anything else is editable via the JSON
// view at the bottom — kept narrow on purpose, so users edit the meaningful
// dials without facing 30 form rows on first open.
const SCALAR_FIELDS: { key: string; label: string; kind: "percent" | "money" | "int"; help?: string }[] = [
  { key: "standard_rate", label: "Income tax — standard rate", kind: "percent" },
  { key: "higher_rate", label: "Income tax — higher rate", kind: "percent" },
  { key: "srco_single", label: "SRCO (single, €)", kind: "money", help: "Standard Rate Cut-Off — income up to this is taxed at the standard rate." },
  { key: "srco_married_one_income", label: "SRCO (married, one income, €)", kind: "money" },
  { key: "credit_personal_single", label: "Credit: personal (single, €)", kind: "money" },
  { key: "credit_personal_married", label: "Credit: personal (married, €)", kind: "money" },
  { key: "credit_paye_employee", label: "Credit: PAYE employee (€)", kind: "money" },
  { key: "prsi_employee_rate", label: "PRSI rate (employee)", kind: "percent" },
  { key: "prsi_self_employed_rate", label: "PRSI rate (self-employed)", kind: "percent" },
  { key: "cgt_rate", label: "CGT rate", kind: "percent" },
  { key: "cgt_annual_exemption", label: "CGT annual exemption (€)", kind: "money" },
  { key: "etf_exit_tax_rate", label: "ETF exit tax rate", kind: "percent" },
  { key: "etf_deemed_disposal_years", label: "ETF deemed disposal interval (years)", kind: "int" },
  { key: "pension_earnings_cap", label: "Pension earnings cap (€)", kind: "money" },
  { key: "pension_tax_free_lump_sum_limit", label: "Pension lump sum tax-free (€)", kind: "money" },
  { key: "pension_lump_sum_reduced_rate", label: "Pension lump sum reduced rate", kind: "percent" },
  { key: "standard_fund_threshold", label: "Standard Fund Threshold (€)", kind: "money" },
];

export function TaxRulesPane({ planId }: { planId: number }) {
  const { data: plan } = usePlan(planId);
  const { data: configs } = useTaxConfigs();
  const updatePlan = useUpdatePlan(planId);
  const createConfig = useCreateTaxConfig();
  const updateConfig = useUpdateTaxConfig();
  const deleteConfig = useDeleteTaxConfig();

  const activeId = plan?.tax_config_id ?? null;
  const officialConfig = configs?.find((c) => c.is_official) ?? null;
  const active: TaxConfigSummary | null = useMemo(() => {
    if (!configs) return null;
    if (activeId == null) return officialConfig;
    return configs.find((c) => c.id === activeId) ?? officialConfig;
  }, [activeId, configs, officialConfig]);

  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => {
    setDraft(active?.config ? { ...active.config } : null);
  }, [active?.id]);

  if (!plan || !configs || !active) {
    return <p className="muted">Loading…</p>;
  }

  const dirty =
    !!draft && JSON.stringify(draft) !== JSON.stringify(active.config);
  const editable = !active.is_official;

  const onCloneActive = async () => {
    const suggested = `${active.name} (my copy)`;
    const input = window.prompt("Name for the new tax-rule set:", suggested);
    if (input === null) return;
    const name = input.trim() || suggested;
    const created = await createConfig.mutateAsync({
      name,
      clone_from_id: active.id,
    });
    await updatePlan.mutateAsync({ tax_config_id: created.id });
  };

  const onSelectActive = async (id: string) => {
    const next = id === "" ? null : Number(id);
    await updatePlan.mutateAsync({ tax_config_id: next });
  };

  const onSave = async () => {
    if (!editable || !draft) return;
    await updateConfig.mutateAsync({ id: active.id, body: { config: draft } });
  };

  const onResetToOfficial = async () => {
    await updatePlan.mutateAsync({ tax_config_id: null });
  };

  const onDelete = async () => {
    if (!editable) return;
    if (!confirm(`Delete tax config "${active.name}"? Plans pinned to it will fall back to the official.`)) return;
    await deleteConfig.mutateAsync(active.id);
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>
          Active tax rules
          <HelpTip>
            Each plan can pin its own tax-rule set. The seeded "Ireland 2026 (official)" is
            read-only; clone it to forecast Budget 2027, model a 50% top rate, or run any
            other what-if. Changes propagate immediately to this plan's projection.
          </HelpTip>
        </h3>
        <div className="field" style={{ maxWidth: 420 }}>
          <label>Pin to</label>
          <select value={activeId ?? ""} onChange={(e) => onSelectActive(e.target.value)}>
            <option value="">Ireland 2026 (official) — default</option>
            {configs
              .filter((c) => !c.is_official)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </div>

        <p className="muted" style={{ marginTop: 8, marginBottom: 8 }}>
          Currently using <strong>{active.name}</strong>
          {active.is_official && (
            <span
              style={{
                marginLeft: 8,
                background: "#dcfce7",
                color: "#166534",
                padding: "2px 8px",
                borderRadius: 999,
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              Official · read-only
            </span>
          )}
        </p>

        <div className="row" style={{ gap: 6 }}>
          <button
            className="btn"
            onClick={onCloneActive}
            disabled={createConfig.isPending}
          >
            {active.is_official ? "Make a copy I can edit" : "Duplicate this config"}
          </button>
          {activeId != null && (
            <button className="btn btn-secondary" onClick={onResetToOfficial}>
              Reset to official
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <h3 style={{ marginTop: 0, marginBottom: 0 }}>Tax-rule fields</h3>
          {editable && (
            <div className="row" style={{ gap: 6 }}>
              <button className="btn" disabled={!dirty || updateConfig.isPending} onClick={onSave}>
                {dirty ? "Save changes" : "Saved"}
              </button>
              <button className="btn btn-secondary" onClick={onDelete}>
                Delete config
              </button>
            </div>
          )}
        </div>
        {!editable && (
          <p className="muted">
            Read-only view of the official ruleset. Use <strong>Make a copy I can edit</strong>
            above to fork it.
          </p>
        )}
        <ResponsiveTable
          rows={SCALAR_FIELDS}
          getKey={(f) => f.key}
          cardTitle={(f) => (
            <>
              {f.label}
              {f.help && <HelpTip>{f.help}</HelpTip>}
            </>
          )}
          columns={[
            {
              header: "Field",
              cell: (f) => (
                <>
                  {f.label}
                  {f.help && <HelpTip>{f.help}</HelpTip>}
                </>
              ),
              hideOnMobile: true,
            },
            {
              header: "Value",
              cell: (f) => {
                const value = draft?.[f.key] ?? active.config[f.key];
                return (
                  <ScalarInput
                    kind={f.kind}
                    value={value}
                    readOnly={!editable}
                    onChange={(v) =>
                      setDraft((d) => ({ ...(d ?? active.config), [f.key]: v }))
                    }
                  />
                );
              },
            },
          ]}
        />


        <p style={{ marginTop: 16 }}>
          <button className="btn btn-secondary" onClick={() => setShowJson((s) => !s)}>
            {showJson ? "Hide" : "Show"} full JSON
          </button>
        </p>
        {showJson && (
          <pre
            style={{
              background: "#0f172a",
              color: "#f8fafc",
              padding: 12,
              borderRadius: 6,
              fontSize: 11,
              overflow: "auto",
              maxHeight: 360,
            }}
          >
            {JSON.stringify(draft ?? active.config, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function ScalarInput({
  kind,
  value,
  readOnly,
  onChange,
}: {
  kind: "percent" | "money" | "int";
  value: unknown;
  readOnly: boolean;
  onChange: (v: unknown) => void;
}) {
  const raw = Number(value ?? 0);
  const style = {
    padding: "4px 8px",
    border: "1px solid #cbd5e1",
    borderRadius: 4,
    width: "100%",
    maxWidth: kind === "percent" ? 130 : 160,
  };

  if (kind === "percent") {
    return (
      <NumericInput
        style={style}
        readOnly={readOnly}
        value={raw * 100}
        onChange={(v) => !readOnly && Number.isFinite(v) && onChange(v / 100)}
      />
    );
  }
  return (
    <NumericInput
      style={style}
      integer={kind === "int"}
      readOnly={readOnly}
      value={raw}
      onChange={(v) => !readOnly && Number.isFinite(v) && onChange(v)}
    />
  );
}
