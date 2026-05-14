import type {
  AssetDraft,
  GoalDraft,
  IncomeDraft,
  LiabilityDraft,
  PersonDraft,
  PlanDraft,
  WizardState,
  WizardStepId,
} from "./store";

export function validatePlan(p: PlanDraft): string[] {
  const errs: string[] = [];
  if (!p.name || !p.name.trim()) errs.push("Plan name is required");
  const by = p.base_year ?? 0;
  if (!Number.isFinite(by) || by < 2000 || by > 2100) errs.push("Base year must be 2000–2100");
  const py = p.projection_years ?? 0;
  if (!Number.isFinite(py) || py < 1 || py > 80) errs.push("Projection years must be 1–80");
  return errs;
}

export function validatePerson(p: PersonDraft): string[] {
  const errs: string[] = [];
  if (!p.name || !p.name.trim()) errs.push("Name is required");
  if (!p.dob || !/^\d{4}-\d{2}-\d{2}$/.test(p.dob)) errs.push("Date of birth is required");
  return errs;
}

export function validateIncome(i: IncomeDraft, plan: PlanDraft): string[] {
  const errs: string[] = [];
  if (!i.name || !i.name.trim()) errs.push("Income name is required");
  if (!Number.isFinite(i.gross_amount) || i.gross_amount < 0) errs.push("Gross amount must be ≥ 0");
  if (!Number.isFinite(i.start_year)) errs.push("Start year is required");
  if (i.end_year != null && i.end_year < i.start_year) errs.push("End year must be ≥ start year");
  const by = plan.base_year ?? 0;
  const py = plan.projection_years ?? 0;
  const max = by + py + 1;
  if (i.start_year < by - 50 || i.start_year > max) errs.push("Start year out of plan range");
  return errs;
}

export function validateAsset(a: AssetDraft): string[] {
  const errs: string[] = [];
  if (!a.name || !a.name.trim()) errs.push("Asset name is required");
  if (!a.kind) errs.push("Asset kind is required");
  if (!Number.isFinite(a.value) || a.value < 0) errs.push("Value must be ≥ 0");
  return errs;
}

export function validateLiability(l: LiabilityDraft): string[] {
  const errs: string[] = [];
  if (!l.name || !l.name.trim()) errs.push("Liability name is required");
  if (!l.kind) errs.push("Liability kind is required");
  if (!Number.isFinite(l.principal) || l.principal <= 0) errs.push("Principal must be > 0");
  if (!Number.isFinite(l.interest_rate) || l.interest_rate < 0 || l.interest_rate > 1)
    errs.push("Interest rate must be between 0 and 1");
  if (!Number.isFinite(l.term_months) || l.term_months <= 0 || l.term_months > 600)
    errs.push("Term must be 1–600 months");
  if (!Number.isFinite(l.start_year)) errs.push("Start year is required");
  return errs;
}

export function validateGoal(g: GoalDraft): string[] {
  const errs: string[] = [];
  if (!g.name || !g.name.trim()) errs.push("Goal name is required");
  if (!g.kind) errs.push("Goal kind is required");
  if (!Number.isFinite(g.target_amount) || g.target_amount < 0)
    errs.push("Target amount must be ≥ 0");
  if (!Number.isFinite(g.target_year)) errs.push("Target year is required");
  return errs;
}

export function canAdvance(step: WizardStepId, s: WizardState): boolean {
  switch (step) {
    case "plan":
      return validatePlan(s.plan).length === 0;
    case "people": {
      if (s.people.length === 0) return false;
      const primaries = s.people.filter((p) => p.is_primary).length;
      if (primaries !== 1) return false;
      return s.people.every((p) => validatePerson(p).length === 0);
    }
    case "income":
      return s.incomes.every((i) => validateIncome(i, s.plan).length === 0);
    case "assets":
      return s.assets.every((a) => validateAsset(a).length === 0);
    case "properties":
      return s.properties.every((a) => validateAsset(a).length === 0);
    case "liabilities":
      return s.liabilities.every((l) => validateLiability(l).length === 0);
    case "goals":
      return s.goals.every((g) => validateGoal(g).length === 0);
    case "review":
      return (
        validatePlan(s.plan).length === 0 &&
        s.people.length >= 1 &&
        s.people.every((p) => validatePerson(p).length === 0) &&
        s.incomes.every((i) => validateIncome(i, s.plan).length === 0) &&
        s.assets.every((a) => validateAsset(a).length === 0) &&
        s.properties.every((a) => validateAsset(a).length === 0) &&
        s.liabilities.every((l) => validateLiability(l).length === 0) &&
        s.goals.every((g) => validateGoal(g).length === 0)
      );
  }
}
