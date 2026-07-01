import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Asset,
  AssetCreate,
  AssetUpdate,
  Assumptions,
  AssumptionsUpsert,
  Benefit,
  BenefitCreate,
  BenefitUpdate,
  Bequest,
  BequestCreate,
  BequestUpdate,
  Child,
  ChildCreate,
  ChildUpdate,
  CompareResponse,
  MonteCarloResponse,
  Expense,
  ExpenseCreate,
  ExpenseUpdate,
  Goal,
  GoalCreate,
  GoalUpdate,
  IncomeSource,
  IncomeSourceCreate,
  IncomeSourceUpdate,
  Liability,
  LiabilityCreate,
  LiabilityUpdate,
  LifePolicy,
  LifePolicyCreate,
  LifePolicyUpdate,
  Person,
  PersonCreate,
  PersonUpdate,
  Plan,
  PlanCreate,
  PlanInvite,
  PlanInvitePreview,
  PlanMember,
  PlanRole,
  PlanUpdate,
  ProjectionResponse,
  Scenario,
  ScenarioCreate,
  ScenarioUpdate,
  TaxConfigCreatePayload,
  TaxConfigSummary,
} from "./types";

const keys = {
  plans: ["plans"] as const,
  plan: (id: number) => ["plan", id] as const,
  people: (planId: number) => ["plan", planId, "people"] as const,
  assumptions: (planId: number) => ["plan", planId, "assumptions"] as const,
  income: (personId: number) => ["person", personId, "income"] as const,
  expenses: (planId: number) => ["plan", planId, "expenses"] as const,
  assets: (planId: number) => ["plan", planId, "assets"] as const,
  liabilities: (planId: number) => ["plan", planId, "liabilities"] as const,
  goals: (planId: number) => ["plan", planId, "goals"] as const,
  scenarios: (planId: number) => ["plan", planId, "scenarios"] as const,
  bequests: (planId: number) => ["plan", planId, "bequests"] as const,
  children: (planId: number) => ["plan", planId, "children"] as const,
  benefits: (planId: number) => ["plan", planId, "benefits"] as const,
  lifePolicies: (planId: number) => ["plan", planId, "life-policies"] as const,
  members: (planId: number) => ["plan", planId, "members"] as const,
  invites: (planId: number) => ["plan", planId, "invites"] as const,
  taxConfigs: () => ["tax-configs"] as const,
  monteCarlo: (planId: number, n: number) => ["plan", planId, "montecarlo", n] as const,
  projection: (planId: number, scenarioId?: number | null) =>
    ["plan", planId, "projection", scenarioId ?? "base"] as const,
  compare: (planId: number, a: number | null, b: number | null) =>
    ["plan", planId, "compare", a ?? "base", b ?? "base"] as const,
};

export function usePlans() {
  return useQuery({ queryKey: keys.plans, queryFn: () => api.get<Plan[]>("/plans") });
}

export function usePlan(id: number) {
  return useQuery({
    queryKey: keys.plan(id),
    queryFn: () => api.get<Plan>(`/plans/${id}`),
    enabled: Number.isFinite(id),
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plans,
    mutationFn: (body: PlanCreate) => api.post<Plan>("/plans", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

export function useUpdatePlan(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(id),
    mutationFn: (body: PlanUpdate) => api.patch<Plan>(`/plans/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.plans });
      qc.invalidateQueries({ queryKey: keys.plan(id) });
    },
  });
}

export function useDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plans,
    mutationFn: (id: number) => api.del(`/plans/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

export function useClonePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plans,
    mutationFn: ({ id, name }: { id: number; name?: string }) =>
      api.post<Plan>(`/plans/${id}/clone`, name ? { name } : {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

export function exportPlan(id: number): Promise<Record<string, unknown>> {
  return api.get<Record<string, unknown>>(`/plans/${id}/export`);
}

export function useImportPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plans,
    mutationFn: (payload: Record<string, unknown>) =>
      api.post<Plan>("/plans/import", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

export function usePeople(planId: number) {
  return useQuery({
    queryKey: keys.people(planId),
    queryFn: () => api.get<Person[]>(`/plans/${planId}/people`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreatePerson(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: PersonCreate) => api.post<Person>(`/plans/${planId}/people`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.people(planId) }),
  });
}

export function useDeletePerson(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (personId: number) => api.del(`/people/${personId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.people(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdatePerson(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: PersonUpdate }) =>
      api.patch<Person>(`/people/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.people(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useAssumptions(planId: number) {
  return useQuery({
    queryKey: keys.assumptions(planId),
    queryFn: () => api.get<Assumptions>(`/plans/${planId}/assumptions`),
    enabled: Number.isFinite(planId),
  });
}

export function useUpsertAssumptions(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: AssumptionsUpsert) =>
      api.put<Assumptions>(`/plans/${planId}/assumptions`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.assumptions(planId) });
      qc.invalidateQueries({ queryKey: keys.projection(planId) });
    },
  });
}

function invalidateProjection(qc: ReturnType<typeof useQueryClient>, planId: number) {
  // Invalidate all projection variants (base + every scenario) and compare results.
  qc.invalidateQueries({ queryKey: ["plan", planId, "projection"] });
  qc.invalidateQueries({ queryKey: ["plan", planId, "compare"] });
}

export function useIncomeFor(personId: number) {
  return useQuery({
    queryKey: keys.income(personId),
    queryFn: () => api.get<IncomeSource[]>(`/people/${personId}/income`),
    enabled: Number.isFinite(personId),
  });
}

export function useCreateIncome(personId: number, planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: IncomeSourceCreate) =>
      api.post<IncomeSource>(`/people/${personId}/income`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.income(personId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteIncome(personId: number, planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (incomeId: number) => api.del(`/income/${incomeId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.income(personId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateIncome(personId: number, planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: IncomeSourceUpdate }) =>
      api.patch<IncomeSource>(`/income/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.income(personId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useExpenses(planId: number) {
  return useQuery({
    queryKey: keys.expenses(planId),
    queryFn: () => api.get<Expense[]>(`/plans/${planId}/expenses`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateExpense(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: ExpenseCreate) => api.post<Expense>(`/plans/${planId}/expenses`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.expenses(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteExpense(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/expenses/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.expenses(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateExpense(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: ExpenseUpdate }) =>
      api.patch<Expense>(`/expenses/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.expenses(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useAssets(planId: number) {
  return useQuery({
    queryKey: keys.assets(planId),
    queryFn: () => api.get<Asset[]>(`/plans/${planId}/assets`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateAsset(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: AssetCreate) => api.post<Asset>(`/plans/${planId}/assets`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.assets(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteAsset(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/assets/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.assets(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateAsset(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: AssetUpdate }) =>
      api.patch<Asset>(`/assets/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.assets(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useLiabilities(planId: number) {
  return useQuery({
    queryKey: keys.liabilities(planId),
    queryFn: () => api.get<Liability[]>(`/plans/${planId}/liabilities`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateLiability(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: LiabilityCreate) =>
      api.post<Liability>(`/plans/${planId}/liabilities`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.liabilities(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteLiability(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/liabilities/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.liabilities(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateLiability(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: LiabilityUpdate }) =>
      api.patch<Liability>(`/liabilities/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.liabilities(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useGoals(planId: number) {
  return useQuery({
    queryKey: keys.goals(planId),
    queryFn: () => api.get<Goal[]>(`/plans/${planId}/goals`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateGoal(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: GoalCreate) => api.post<Goal>(`/plans/${planId}/goals`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.goals(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateGoal(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: GoalUpdate }) =>
      api.patch<Goal>(`/goals/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.goals(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteGoal(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/goals/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.goals(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useProjection(planId: number, scenarioId?: number | null) {
  const qs = scenarioId ? `?scenario_id=${scenarioId}` : "";
  return useQuery({
    queryKey: keys.projection(planId, scenarioId ?? null),
    queryFn: () => api.get<ProjectionResponse>(`/plans/${planId}/projection${qs}`),
    enabled: Number.isFinite(planId),
  });
}

export function useScenarios(planId: number) {
  return useQuery({
    queryKey: keys.scenarios(planId),
    queryFn: () => api.get<Scenario[]>(`/plans/${planId}/scenarios`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateScenario(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: ScenarioCreate) =>
      api.post<Scenario>(`/plans/${planId}/scenarios`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.scenarios(planId) }),
  });
}

export function useUpdateScenario(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: ScenarioUpdate }) =>
      api.patch<Scenario>(`/scenarios/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.scenarios(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteScenario(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/scenarios/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.scenarios(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useCompare(planId: number, a: number | null, b: number | null) {
  const qs = new URLSearchParams();
  if (a != null) qs.set("a", String(a));
  if (b != null) qs.set("b", String(b));
  const qsStr = qs.toString();
  return useQuery({
    queryKey: keys.compare(planId, a, b),
    queryFn: () =>
      api.get<CompareResponse>(`/plans/${planId}/compare${qsStr ? `?${qsStr}` : ""}`),
    enabled: Number.isFinite(planId),
  });
}

// ---------- Monte Carlo ----------

export function useMonteCarlo(
  planId: number,
  opts?: { enabled?: boolean; n?: number; seed?: number | null },
) {
  const n = opts?.n ?? 200;
  const seed = opts?.seed ?? null;
  const seedQs = seed !== null ? `&seed=${seed}` : "";
  return useQuery({
    queryKey: [...keys.monteCarlo(planId, n), seed],
    queryFn: () =>
      api.get<MonteCarloResponse>(`/plans/${planId}/projection/montecarlo?n=${n}${seedQs}`),
    enabled: (opts?.enabled ?? true) && Number.isFinite(planId),
    staleTime: 60_000, // MC is expensive — keep cached for 1 minute
  });
}

// ---------- Bequests ----------

export function useBequests(planId: number) {
  return useQuery({
    queryKey: keys.bequests(planId),
    queryFn: () => api.get<Bequest[]>(`/plans/${planId}/bequests`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateBequest(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: BequestCreate) => api.post<Bequest>(`/plans/${planId}/bequests`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.bequests(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateBequest(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: BequestUpdate }) =>
      api.patch<Bequest>(`/bequests/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.bequests(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteBequest(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/bequests/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.bequests(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

// ---------- Children ----------

export function useChildren(planId: number) {
  return useQuery({
    queryKey: keys.children(planId),
    queryFn: () => api.get<Child[]>(`/plans/${planId}/children`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateChild(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: ChildCreate) => api.post<Child>(`/plans/${planId}/children`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.children(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateChild(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: ChildUpdate }) =>
      api.patch<Child>(`/children/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.children(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteChild(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/children/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.children(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

// ---------- Benefits (benefit-in-kind) ----------

export function useBenefits(planId: number) {
  return useQuery({
    queryKey: keys.benefits(planId),
    queryFn: () => api.get<Benefit[]>(`/plans/${planId}/benefits`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateBenefit(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: BenefitCreate) => api.post<Benefit>(`/plans/${planId}/benefits`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.benefits(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateBenefit(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: BenefitUpdate }) =>
      api.patch<Benefit>(`/benefits/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.benefits(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteBenefit(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/benefits/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.benefits(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

// ---------- Life policies (protection) ----------

export function useLifePolicies(planId: number) {
  return useQuery({
    queryKey: keys.lifePolicies(planId),
    queryFn: () => api.get<LifePolicy[]>(`/plans/${planId}/life-policies`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateLifePolicy(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: LifePolicyCreate) =>
      api.post<LifePolicy>(`/plans/${planId}/life-policies`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.lifePolicies(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useUpdateLifePolicy(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ id, body }: { id: number; body: LifePolicyUpdate }) =>
      api.patch<LifePolicy>(`/life-policies/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.lifePolicies(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

export function useDeleteLifePolicy(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (id: number) => api.del(`/life-policies/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.lifePolicies(planId) });
      invalidateProjection(qc, planId);
    },
  });
}

// ---------- Sharing (members + invites) ----------

export function useMembers(planId: number) {
  return useQuery({
    queryKey: keys.members(planId),
    queryFn: () => api.get<PlanMember[]>(`/plans/${planId}/members`),
    enabled: Number.isFinite(planId),
  });
}

export function useUpdateMemberRole(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: ({ userId, role }: { userId: number; role: PlanRole }) =>
      api.patch<PlanMember>(`/plans/${planId}/members/${userId}`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.members(planId) }),
  });
}

export function useRemoveMember(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (userId: number) => api.del(`/plans/${planId}/members/${userId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.members(planId) });
      qc.invalidateQueries({ queryKey: keys.plans });
    },
  });
}

export function useInvites(planId: number) {
  return useQuery({
    queryKey: keys.invites(planId),
    queryFn: () => api.get<PlanInvite[]>(`/plans/${planId}/invites`),
    enabled: Number.isFinite(planId),
  });
}

export function useCreateInvite(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (body: { role: PlanRole; email?: string | null; expires_days?: number }) =>
      api.post<PlanInvite>(`/plans/${planId}/invites`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.invites(planId) }),
  });
}

export function useRevokeInvite(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plan(planId),
    mutationFn: (inviteId: number) => api.del(`/invites/${inviteId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.invites(planId) }),
  });
}

export function usePreviewInvite(token: string) {
  return useQuery({
    queryKey: ["invite-preview", token],
    queryFn: () => api.get<PlanInvitePreview>(`/invites/${token}`),
    enabled: !!token,
    retry: false,
  });
}

export function useAcceptInvite() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.plans,
    mutationFn: (token: string) => api.post<PlanInvite>(`/invites/${token}/accept`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.plans }),
  });
}

// ---------- Tax configs ----------

export function useTaxConfigs() {
  return useQuery({
    queryKey: keys.taxConfigs(),
    queryFn: () => api.get<TaxConfigSummary[]>("/tax-configs"),
  });
}

export function useCreateTaxConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.taxConfigs(),
    mutationFn: (body: TaxConfigCreatePayload) =>
      api.post<TaxConfigSummary>("/tax-configs", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.taxConfigs() }),
  });
}

export function useUpdateTaxConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.taxConfigs(),
    mutationFn: ({ id, body }: { id: number; body: { name?: string; config?: Record<string, unknown> } }) =>
      api.patch<TaxConfigSummary>(`/tax-configs/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.taxConfigs() });
      // Any plan pinned to this config needs its projection refetched.
      qc.invalidateQueries({ queryKey: ["plan"] });
    },
  });
}

export function useDeleteTaxConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: keys.taxConfigs(),
    mutationFn: (id: number) => api.del(`/tax-configs/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.taxConfigs() });
      qc.invalidateQueries({ queryKey: keys.plans });
      qc.invalidateQueries({ queryKey: ["plan"] });
    },
  });
}
