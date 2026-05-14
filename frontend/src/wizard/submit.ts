import { api } from "../api/client";
import type {
  Asset,
  AssetCreate,
  Expense,
  ExpenseCreate,
  Goal,
  GoalCreate,
  IncomeSource,
  IncomeSourceCreate,
  Liability,
  LiabilityCreate,
  Person,
  PersonCreate,
  Plan,
  PlanCreate,
} from "../api/types";

import type { DraftId, WizardState } from "./store";

export type SubmitPhase =
  | "plan"
  | "people"
  | "income"
  | "assets"
  | "liabilities"
  | "expenses"
  | "goals"
  | "done";

export interface SubmitError {
  draftId: DraftId | "plan";
  phase: SubmitPhase;
  message: string;
}

export interface SubmitProgress {
  phase: SubmitPhase;
  completed: number;
  total: number;
  serverIds: Record<DraftId, number>;
  errors: SubmitError[];
}

export interface SubmitResult {
  planId: number | null;
  serverIds: Record<DraftId, number>;
  errors: SubmitError[];
}

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

function stripWizardKeys<T extends { draftId?: unknown }>(draft: T): Omit<T, "draftId"> {
  const { draftId: _draftId, ...rest } = draft;
  return rest;
}

function toPersonCreate(d: WizardState["people"][number]): PersonCreate {
  const { draftId: _i, ...rest } = d;
  return rest;
}
function toIncomeCreate(d: WizardState["incomes"][number]): IncomeSourceCreate {
  const { draftId: _i, personDraftId: _p, isBonus: _b, ...rest } = d;
  return rest;
}
function toAssetCreate(d: WizardState["assets"][number]): AssetCreate {
  const { draftId: _i, ownerPersonDraftId: _o, ...rest } = d;
  return rest;
}
function toLiabilityCreate(d: WizardState["liabilities"][number]): LiabilityCreate {
  const { draftId: _i, linkedPropertyDraftId: _p, ...rest } = d;
  return rest;
}
function toExpenseCreate(d: WizardState["expenses"][number]): ExpenseCreate {
  const { draftId: _i, ownerPersonDraftId: _o, ...rest } = d;
  return rest;
}
function toGoalCreate(d: WizardState["goals"][number]): GoalCreate {
  const { draftId: _i, linkedPersonDraftId: _p, ...rest } = d;
  return rest;
}

export async function submitWizard(
  state: WizardState,
  prior: SubmitResult | null,
  onProgress: (p: SubmitProgress) => void,
): Promise<SubmitResult> {
  const serverIds: Record<DraftId, number> = { ...(prior?.serverIds ?? {}) };
  const errors: SubmitError[] = [];
  let planId: number | null = prior?.planId ?? null;

  const totalRows =
    1 +
    state.people.length +
    state.incomes.length +
    state.assets.length +
    state.properties.length +
    state.liabilities.length +
    state.expenses.length +
    state.goals.length;
  let completed = 0;
  const report = (phase: SubmitPhase) =>
    onProgress({ phase, completed, total: totalRows, serverIds, errors });

  // Phase: plan
  if (planId == null) {
    try {
      const body: PlanCreate = {
        name: state.plan.name.trim(),
        base_year: state.plan.base_year,
        projection_years: state.plan.projection_years,
        tax_config_id: state.plan.tax_config_id ?? null,
        filing_status: state.plan.filing_status ?? null,
      };
      const plan = await api.post<Plan>("/plans", body);
      planId = plan.id;
    } catch (e) {
      errors.push({ draftId: "plan", phase: "plan", message: errMessage(e) });
      report("plan");
      return { planId: null, serverIds, errors };
    }
  }
  completed += 1;
  report("plan");

  // Phase: people (parallel)
  await Promise.all(
    state.people.map(async (p) => {
      if (serverIds[p.draftId] != null) return;
      try {
        const created = await api.post<Person>(`/plans/${planId}/people`, toPersonCreate(p));
        serverIds[p.draftId] = created.id;
      } catch (e) {
        errors.push({ draftId: p.draftId, phase: "people", message: errMessage(e) });
      } finally {
        completed += 1;
        report("people");
      }
    }),
  );

  // Phase: income (per person, parallel within phase)
  await Promise.all(
    state.incomes.map(async (i) => {
      if (serverIds[i.draftId] != null) {
        completed += 1;
        report("income");
        return;
      }
      const personId = serverIds[i.personDraftId];
      if (personId == null) {
        errors.push({
          draftId: i.draftId,
          phase: "income",
          message: "Owning person failed to create",
        });
        completed += 1;
        report("income");
        return;
      }
      try {
        const created = await api.post<IncomeSource>(
          `/people/${personId}/income`,
          toIncomeCreate(i),
        );
        serverIds[i.draftId] = created.id;
      } catch (e) {
        errors.push({ draftId: i.draftId, phase: "income", message: errMessage(e) });
      } finally {
        completed += 1;
        report("income");
      }
    }),
  );

  // Phase: assets + properties (same backend endpoint)
  const assetDrafts = [...state.assets, ...state.properties];
  await Promise.all(
    assetDrafts.map(async (a) => {
      if (serverIds[a.draftId] != null) {
        completed += 1;
        report("assets");
        return;
      }
      const payload = toAssetCreate(a);
      if (a.ownerPersonDraftId) {
        const ownerId = serverIds[a.ownerPersonDraftId];
        if (ownerId != null) payload.owner_person_id = ownerId;
      }
      try {
        const created = await api.post<Asset>(`/plans/${planId}/assets`, payload);
        serverIds[a.draftId] = created.id;
      } catch (e) {
        errors.push({ draftId: a.draftId, phase: "assets", message: errMessage(e) });
      } finally {
        completed += 1;
        report("assets");
      }
    }),
  );

  // Phase: liabilities (parallel)
  await Promise.all(
    state.liabilities.map(async (l) => {
      if (serverIds[l.draftId] != null) {
        completed += 1;
        report("liabilities");
        return;
      }
      try {
        const created = await api.post<Liability>(
          `/plans/${planId}/liabilities`,
          toLiabilityCreate(l),
        );
        serverIds[l.draftId] = created.id;
      } catch (e) {
        errors.push({ draftId: l.draftId, phase: "liabilities", message: errMessage(e) });
      } finally {
        completed += 1;
        report("liabilities");
      }
    }),
  );

  // Phase: expenses (parallel)
  await Promise.all(
    state.expenses.map(async (e) => {
      if (serverIds[e.draftId] != null) {
        completed += 1;
        report("expenses");
        return;
      }
      const payload = toExpenseCreate(e);
      if (e.ownerPersonDraftId) {
        const ownerId = serverIds[e.ownerPersonDraftId];
        if (ownerId != null) payload.owner_person_id = ownerId;
      }
      try {
        const created = await api.post<Expense>(`/plans/${planId}/expenses`, payload);
        serverIds[e.draftId] = created.id;
      } catch (err) {
        errors.push({ draftId: e.draftId, phase: "expenses", message: errMessage(err) });
      } finally {
        completed += 1;
        report("expenses");
      }
    }),
  );

  // Phase: goals (parallel)
  await Promise.all(
    state.goals.map(async (g) => {
      if (serverIds[g.draftId] != null) {
        completed += 1;
        report("goals");
        return;
      }
      const payload = toGoalCreate(g);
      if (g.linkedPersonDraftId) {
        const linkedId = serverIds[g.linkedPersonDraftId];
        if (linkedId != null) payload.linked_person_id = linkedId;
      }
      try {
        const created = await api.post<Goal>(`/plans/${planId}/goals`, payload);
        serverIds[g.draftId] = created.id;
      } catch (e) {
        errors.push({ draftId: g.draftId, phase: "goals", message: errMessage(e) });
      } finally {
        completed += 1;
        report("goals");
      }
    }),
  );

  report("done");
  return { planId, serverIds, errors };
}

// Re-export for completeness; suppress unused-import warning in build.
export { stripWizardKeys };
