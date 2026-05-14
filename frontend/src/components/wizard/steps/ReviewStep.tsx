import { Link } from "react-router-dom";

import { fmtMoney, fmtPctDisplay } from "../../../lib/format";
import { useWizard, type AssetDraft, type DraftId, type PersonDraft } from "../../../wizard/store";
import type { SubmitProgress } from "../../../wizard/submit";

const ASSET_KIND_LABELS: Record<string, string> = {
  cash: "Cash",
  deposit: "Deposit",
  investment_unwrapped: "Investment account",
  etf_fund: "ETF / fund",
  prsa: "PRSA",
  occupational_pension: "Occupational pension",
  arf: "ARF",
  property_primary: "Primary residence",
  property_btl: "Buy-to-let",
};

const INCOME_KIND_LABELS: Record<string, string> = {
  employment: "Employment",
  self_employment: "Self-employment",
  rental: "Rental",
  state_pension: "State pension",
  private_pension_drawdown: "Private pension drawdown",
  annuity: "Annuity",
  homecaring: "Home-caring",
  other: "Other",
};

const GOAL_KIND_LABELS: Record<string, string> = {
  retirement: "Retirement nest egg",
  pre_retirement_spend: "Pre-retirement spend",
  milestone: "Milestone",
  education: "Education",
  net_worth: "Net worth target",
  gift: "Gift",
};

const FILING_LABELS: Record<string, string> = {
  single: "Single",
  married: "Married / civil partnership",
  cohabiting: "Cohabiting",
};

const EXPENSE_CATEGORY_LABELS: Record<string, string> = {
  basic: "Basic",
  discretionary: "Discretionary",
  single_year: "One-off",
  legacy: "Legacy",
};

export function ReviewStep({ progress }: { progress: SubmitProgress | null }) {
  const s = useWizard();
  const personName = (id: DraftId | null | undefined) =>
    s.people.find((p) => p.draftId === id)?.name || "(unassigned)";

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <PlanSummary />

      <Section
        title="People"
        count={s.people.length}
        editStep="people"
        empty="No people added."
      >
        {s.people.map((p) => (
          <PersonCard key={p.draftId} person={p} incomes={s.incomes} />
        ))}
      </Section>

      <Section
        title="Assets"
        count={s.assets.length}
        editStep="assets"
        empty="No assets added."
      >
        {s.assets.map((a) => (
          <RowLine
            key={a.draftId}
            primary={a.name || "(unnamed)"}
            secondary={`${ASSET_KIND_LABELS[a.kind] ?? a.kind} · ${fmtMoney(a.value)}`}
            tertiary={
              a.growth_rate
                ? `Grows ${fmtPctDisplay(a.growth_rate)}/yr · Owner: ${personName(a.ownerPersonDraftId)}`
                : `Owner: ${personName(a.ownerPersonDraftId)}`
            }
          />
        ))}
      </Section>

      <Section
        title="Properties"
        count={s.properties.length}
        editStep="properties"
        empty="No properties added."
      >
        {s.properties.map((p) => (
          <PropertyLine
            key={p.draftId}
            property={p}
            ownerName={personName(p.ownerPersonDraftId)}
            hasMortgage={s.liabilities.some(
              (l) => l.linkedPropertyDraftId === p.draftId,
            )}
          />
        ))}
      </Section>

      <Section
        title="Liabilities"
        count={s.liabilities.length}
        editStep="liabilities"
        empty="No liabilities added."
      >
        {s.liabilities.map((l) => (
          <RowLine
            key={l.draftId}
            primary={l.name || "(unnamed)"}
            secondary={`${l.kind === "mortgage" ? "Mortgage" : "Loan"} · ${fmtMoney(l.principal)} @ ${fmtPctDisplay(l.interest_rate)}`}
            tertiary={`${l.term_months} months from ${l.start_year}${l.monthly_overpayment ? ` · +${fmtMoney(l.monthly_overpayment)}/mo overpayment` : ""}`}
          />
        ))}
      </Section>

      <Section
        title="Expenses"
        count={s.expenses.length}
        editStep="expenses"
        empty="No expenses added."
      >
        {s.expenses.map((e) => {
          const span =
            e.category === "single_year"
              ? `in ${e.start_year}`
              : e.end_year != null
                ? `${e.start_year}–${e.end_year}`
                : `from ${e.start_year}`;
          const infl = e.escalation_rate
            ? ` · ${fmtPctDisplay(e.escalation_rate)} inflation`
            : "";
          return (
            <RowLine
              key={e.draftId}
              primary={e.name || "(unnamed)"}
              secondary={`${EXPENSE_CATEGORY_LABELS[e.category] ?? e.category} · ${fmtMoney(e.amount)}/yr · ${span}${infl}`}
              tertiary={
                e.ownerPersonDraftId
                  ? `Owner: ${personName(e.ownerPersonDraftId)}`
                  : undefined
              }
            />
          );
        })}
      </Section>

      <Section
        title="Goals"
        count={s.goals.length}
        editStep="goals"
        empty="No goals added."
      >
        {s.goals.map((g) => (
          <RowLine
            key={g.draftId}
            primary={g.name || "(unnamed)"}
            secondary={`${GOAL_KIND_LABELS[g.kind] ?? g.kind} · ${fmtMoney(g.target_amount)} by ${g.target_year}`}
            tertiary={
              g.linkedPersonDraftId
                ? `Linked to ${personName(g.linkedPersonDraftId)}`
                : undefined
            }
          />
        ))}
      </Section>

      {progress && <ProgressCard progress={progress} />}
    </div>
  );
}

function PlanSummary() {
  const plan = useWizard((s) => s.plan);
  const filing = plan.filing_status ? FILING_LABELS[plan.filing_status] : "—";
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 style={{ margin: 0 }}>{plan.name || "(unnamed plan)"}</h3>
        <Link to="/plans/new/plan" style={editLinkStyle}>
          Edit
        </Link>
      </div>
      <div style={{ marginTop: 6, color: "#475569", fontSize: 14 }}>
        Base year {plan.base_year} · {plan.projection_years} year projection · {filing}
      </div>
    </div>
  );
}

function PersonCard({
  person,
  incomes,
}: {
  person: PersonDraft;
  incomes: ReturnType<typeof useWizard.getState>["incomes"];
}) {
  const own = incomes.filter((i) => i.personDraftId === person.draftId);
  const dobYear = person.dob ? Number(person.dob.slice(0, 4)) : null;
  const ageBits: string[] = [];
  if (dobYear != null) ageBits.push(`born ${dobYear}`);
  if (person.retirement_age != null) ageBits.push(`retires at ${person.retirement_age}`);
  return (
    <div style={subCardStyle}>
      <div style={{ fontWeight: 600 }}>
        {person.name || "(unnamed)"}
        {person.is_primary && (
          <span
            style={{
              marginLeft: 6,
              fontSize: 11,
              color: "#1d4ed8",
              background: "#dbeafe",
              padding: "2px 6px",
              borderRadius: 4,
            }}
          >
            primary
          </span>
        )}
      </div>
      {ageBits.length > 0 && (
        <div style={{ fontSize: 13, color: "#64748b", marginTop: 2 }}>{ageBits.join(" · ")}</div>
      )}
      {own.length > 0 ? (
        <ul style={{ margin: "8px 0 0", padding: 0, listStyle: "none", display: "grid", gap: 4 }}>
          {own.map((i) => {
            const span =
              i.end_year != null ? `${i.start_year}–${i.end_year}` : `from ${i.start_year}`;
            const esc = i.escalation_rate
              ? ` · ${fmtPctDisplay(i.escalation_rate)}/yr growth`
              : "";
            return (
              <li key={i.draftId} style={{ fontSize: 13, color: "#334155" }}>
                <strong>{i.name}</strong> — {INCOME_KIND_LABELS[i.kind] ?? i.kind} ·{" "}
                {fmtMoney(i.gross_amount)}/yr · {span}
                {esc}
              </li>
            );
          })}
        </ul>
      ) : (
        <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 4 }}>No income sources</div>
      )}
    </div>
  );
}

function PropertyLine({
  property,
  ownerName,
  hasMortgage,
}: {
  property: AssetDraft;
  ownerName: string;
  hasMortgage: boolean;
}) {
  return (
    <RowLine
      primary={property.name || "(unnamed)"}
      secondary={`${ASSET_KIND_LABELS[property.kind] ?? property.kind} · ${fmtMoney(property.value)}`}
      tertiary={[
        property.acquired_year ? `Purchased ${property.acquired_year}` : null,
        property.cost_basis ? `for ${fmtMoney(property.cost_basis)}` : null,
        `Owner: ${ownerName}`,
        hasMortgage ? "Mortgage linked" : null,
      ]
        .filter(Boolean)
        .join(" · ")}
    />
  );
}

function Section({
  title,
  count,
  editStep,
  empty,
  children,
}: {
  title: string;
  count: number;
  editStep: string;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card">
      <div
        className="row"
        style={{ justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}
      >
        <h3 style={{ margin: 0, fontSize: 16 }}>
          {title} <span style={{ color: "#94a3b8", fontWeight: 400 }}>({count})</span>
        </h3>
        <Link to={`/plans/new/${editStep}`} style={editLinkStyle}>
          Edit
        </Link>
      </div>
      {count === 0 ? (
        <div style={{ color: "#94a3b8", fontSize: 14 }}>{empty}</div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>{children}</div>
      )}
    </div>
  );
}

function RowLine({
  primary,
  secondary,
  tertiary,
}: {
  primary: string;
  secondary?: string;
  tertiary?: string;
}) {
  return (
    <div style={subCardStyle}>
      <div style={{ fontWeight: 600 }}>{primary}</div>
      {secondary && (
        <div style={{ fontSize: 13, color: "#475569", marginTop: 2 }}>{secondary}</div>
      )}
      {tertiary && (
        <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{tertiary}</div>
      )}
    </div>
  );
}

function ProgressCard({ progress }: { progress: SubmitProgress }) {
  return (
    <div className="card">
      <h4 style={{ marginTop: 0 }}>Submitting…</h4>
      <div className="muted" style={{ fontSize: 13, color: "#475569" }}>
        Phase: {progress.phase} · {progress.completed}/{progress.total}
      </div>
      <div
        aria-hidden="true"
        style={{
          marginTop: 8,
          height: 6,
          background: "#e2e8f0",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(100, (progress.completed / Math.max(1, progress.total)) * 100)}%`,
            height: "100%",
            background: "#2563eb",
            transition: "width 200ms ease-out",
          }}
        />
      </div>
      {progress.errors.length > 0 && (
        <ul style={{ marginTop: 12, color: "#991b1b", fontSize: 13 }}>
          {progress.errors.map((e, idx) => (
            <li key={idx}>
              [{e.phase}] {e.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const subCardStyle: React.CSSProperties = {
  padding: "10px 12px",
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: 6,
};

const editLinkStyle: React.CSSProperties = {
  fontSize: 13,
  color: "#2563eb",
  textDecoration: "none",
};
