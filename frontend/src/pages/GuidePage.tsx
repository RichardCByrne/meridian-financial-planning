import { Link } from "react-router-dom";

export function GuidePage() {
  return (
    <div style={{ maxWidth: 880 }}>
      <h2 style={{ marginTop: 0 }}>Welcome to Meridian</h2>
      <p className="muted" style={{ fontSize: 15 }}>
        A multi-user financial-planning tool with an Ireland 2026 tax engine. The
        deterministic projection is reproducible; an optional Monte Carlo overlay
        adds probability bands when you want a sense of the spread.
      </p>

      <Section title="In short">
        <p>
          Build a <strong>plan</strong> describing your household: people, income, expenses,
          assets, liabilities, goals, bequests. The simulator runs year-by-year over your
          projection horizon (default 30 years) applying Irish income tax, USC, PRSI, CGT,
          ETF exit tax, CAT (inheritance), and the full pension lifecycle (age-based
          contribution cap → 25% lump sum at retirement → ARF imputed drawdown). The
          <em> Let's See</em> tab visualises the output, with an optional Monte Carlo fan
          chart (p5–p95). <em>Scenarios</em> let you ask "what if…" without disturbing the
          base plan, and <em>Sharing</em> lets you invite a partner or adviser as
          viewer / editor / owner.
        </p>
        <p>
          <Link to="/plans">→ Open the Plans list</Link> to create your first plan, or open an
          existing one.
        </p>
      </Section>

      <Section title="The tabs inside a plan">
        <DefList
          items={[
            ["Let's See", "The main visualisation. Switch between Net worth, Cash flow, Income breakdown, and Tax breakdown. Hover any year to see the full breakdown of income, tax, expenses, and assets. The Probability bands toggle replaces the deterministic line with a Monte Carlo fan chart (p5–p95 spread over 200 runs) plus a median line, and surfaces shortfall probability and median final net worth."],
            ["Timeline", "Drag retirement events and goal pills along a year axis. Releasing the pill commits the change and re-runs the projection."],
            ["People", "The humans in your plan. Date of birth drives ages and state-pension eligibility. Retirement age drives the pension lifecycle (lump sum + ARF drawdown). Rent-credit claim is a per-person flag."],
            ["Income", "Salaries, rentals, self-employment, etc. Each income source has its own start/end year and escalation rate. Pension % is the employee contribution; Employer % stacks on top without reducing your taxable income."],
            ["Expenses", "Recurring or one-off spend. See the One-off events box below for how categories work."],
            ["Assets", "Cash, deposits, ETFs, unwrapped investments, pension wrappers (PRSA / occupational / ARF), and property. Each kind has its own tax treatment when sold or drawn down. AVCs sit on the pension wrapper directly."],
            ["Liabilities", "Mortgages and loans, amortised monthly. Outstanding debt is netted off net worth."],
            ["Goals", "Aspirational targets. Cost-bearing goals (milestone, education, gift, pre-retirement spend) inject as expenses in the target year. Net-worth goals snapshot whether you've hit a number by year X. Retirement goals are informational pins on the timeline — your Person.retirement_age is what actually drives the retirement event."],
            ["Legacy", "Bequests: how each person's estate is split on death. Each bequest names a beneficiary (inside the plan or external) and a CAT group (A / B / C / exempt). CAT is computed against the beneficiary's lifetime running total, and the net inheritance routes to the plan's cash bucket."],
            ["Scenarios", "Field-level overrides on top of the base plan, plus the ability to add new income sources or expenses that don't exist in the base. The base is untouched."],
            ["Compare", "Pick two scenarios (or Base vs a scenario). The simulator runs twice and you get side-by-side net worth, a per-year delta strip, expenses, tax, and a summary table."],
            ["Tax rules", "Pin a TaxConfig to this plan — the seeded Ireland 2026 official is the default. Clone it to a personal copy and tweak bands, rates, or pension caps to forecast a future budget or stress-test a rate change."],
            ["Sharing", "Owner-only. Generate a share-link invite at viewer / editor / owner role. Optionally email-bind the invite so only the named recipient can accept. Revoke a pending invite at any time; list current members in the same pane."],
            ["Assumptions", "Inflation, default growth rates, earnings growth, state pension age, state pension annual amount, and state pension escalation rate (decoupled from general inflation)."],
          ]}
        />
      </Section>

      <Section title="Modelling one-off events">
        <p>
          The platform handles one-off events in three different ways depending on what
          they are:
        </p>
        <DefList
          items={[
            ["A one-off cost (wedding, car, big trip)", "Add an Expense with category set to single_year. It fires only in the start year and does not recur."],
            ["A goal that costs money (education fees, milestone gift)", "Add a Goal of kind milestone, education, gift, or pre_retirement_spend. The target_amount is treated as an expense in target_year and rolls into the cash-flow shortfall logic."],
            ["A windfall (inheritance, bonus, sale proceeds)", "Add an Asset with the cash value at the time it lands — set its acquired_year if you want the simulator to treat it as appearing in that year. Or, in a Scenario, use 'Add income' with category Other and a 1-year window."],
            ["A future income change (promotion, salary cut, side hustle)", "Inside a Scenario, click '+ Add income (e.g. promotion)'. Enter the salary delta (the increase, not the new total) with a start_year. Your base salary keeps running unchanged."],
          ]}
        />
      </Section>

      <Section title="Scenarios in two minutes">
        <ol>
          <li>Build the base plan as accurately as you can.</li>
          <li>
            Open <em>Scenarios</em>, name a scenario (e.g. "Retire at 60"), and either
            override an existing field (retirement_age = 60) or add a new income/expense.
          </li>
          <li>
            Open <em>Compare</em>, pick Base for series A and the new scenario for series B.
            The chart shows net worth diverging year-by-year and the delta strip shows where
            you gain or lose ground.
          </li>
        </ol>
        <p className="muted" style={{ fontSize: 13 }}>
          Scenarios are stored as JSON-Patch overlays — they do not duplicate any rows from
          the base plan. Editing the base plan after creating scenarios is safe; scenarios
          re-resolve against whatever the base looks like at projection time.
        </p>
      </Section>

      <Section title="What this tool does NOT do (yet)">
        <ul>
          <li><strong>AI walkthrough / chatbot.</strong> Phase 14 — not started.</li>
          <li><strong>PDF export.</strong> Reports are screen-only.</li>
          <li><strong>Non-Ireland jurisdictions.</strong> The tax config is parameterised but only the Ireland 2026 ruleset is seeded.</li>
          <li>
            <strong>Tax advice.</strong> Verify Budget 2026 numbers against the Revenue
            sources before relying on any output for a real decision.
          </li>
        </ul>
      </Section>

      <Section title="What's actually there now">
        <ul>
          <li><strong>Multi-user with role-based sharing.</strong> Firebase Auth on the backend; plan owners invite collaborators as viewer / editor / owner via share-link.</li>
          <li><strong>Monte Carlo probability bands</strong> on Let's See — toggle to see the p5–p95 spread of net worth across 200 runs plus the probability of running short.</li>
          <li><strong>CAT / inheritance modelling.</strong> Bequests on the Legacy tab; CAT computed per beneficiary group with lifetime aggregation.</li>
          <li><strong>Multi-tax-year configurable rules.</strong> Clone the seeded Ireland 2026 official config and tweak it to forecast a future budget.</li>
          <li><strong>Plan clone / export / import.</strong> JSON snapshot round-trip preserves people, assets, scenarios, bequests, everything.</li>
        </ul>
      </Section>

      <Section title="Recommended first session">
        <ol>
          <li><Link to="/plans">Create a plan</Link> with your household name and base year (default 2026).</li>
          <li>Add one or two People with their DOB and an honest retirement_age guess.</li>
          <li>Add your salary on Income — set the pension % to your real contribution.</li>
          <li>Add your real recurring expenses and any active mortgage on Liabilities.</li>
          <li>Add your assets (cash + investments + pension wrappers).</li>
          <li>Open Let's See — the chart should look roughly plausible. If a year goes red (shortfall), that's where the model says you'd run out of cash.</li>
          <li>On Goals, add a target net worth or a milestone (e.g. 30k car in 2032).</li>
          <li>Create a "Retire 5 years early" scenario and run Compare.</li>
          <li>On Let's See, toggle <em>Probability bands</em> to see how wide the net-worth spread is once growth and inflation are stochastic.</li>
          <li>If you want a partner or adviser to see it, open <em>Sharing</em> and send a viewer invite.</li>
        </ol>
      </Section>

      <p className="muted" style={{ fontSize: 12, marginTop: 32 }}>
        Inspired by Voyant AdviserGo but not affiliated with Voyant Inc. — no Voyant code or assets.
        No tax advice. Tax constants pinned to Ireland 2026 — verify Budget 2026 numbers before
        relying on any output.
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {children}
    </section>
  );
}

function DefList({ items }: { items: [string, string][] }) {
  return (
    <dl style={{ margin: 0 }}>
      {items.map(([term, def]) => (
        <div key={term} style={{ marginBottom: 12 }}>
          <dt style={{ fontWeight: 600, marginBottom: 2 }}>{term}</dt>
          <dd style={{ margin: 0, color: "#475569", fontSize: 14, lineHeight: 1.5 }}>{def}</dd>
        </div>
      ))}
    </dl>
  );
}
