// Hand-written for Phase 1. Replaced with `openapi-typescript` generation in a later phase.

export type FilingStatus = "single" | "married" | "cohabiting";

export interface Plan {
  id: number;
  name: string;
  base_year: number;
  projection_years: number;
  created_at: string;
  tax_config_id: number | null;
  filing_status: FilingStatus | null;
}

export interface PlanCreate {
  name: string;
  base_year?: number;
  projection_years?: number;
  tax_config_id?: number | null;
  filing_status?: FilingStatus | null;
}

export interface PlanUpdate {
  name?: string;
  base_year?: number;
  projection_years?: number;
  tax_config_id?: number | null;
  filing_status?: FilingStatus | null;
}

export interface TaxConfigSummary {
  id: number;
  name: string;
  is_official: boolean;
  created_by_user_id: number | null;
  created_at: string;
  // Loose typing — config is a dict of tax-rule fields. Critical fields
  // surfaced explicitly below, anything else can be edited via the JSON view.
  config: Record<string, unknown>;
}

export interface TaxConfigCreatePayload {
  name: string;
  clone_from_id?: number | null;
  config?: Record<string, unknown>;
}

export interface Person {
  id: number;
  plan_id: number;
  name: string;
  dob: string; // ISO date
  is_primary: boolean;
  life_expectancy: number;
  gender_for_state_pension: string | null;
  retirement_age: number | null;
  claims_rent_credit: boolean;
  lump_sum_pct: number;
}

export interface PersonCreate {
  name: string;
  dob: string;
  is_primary?: boolean;
  life_expectancy?: number;
  gender_for_state_pension?: string | null;
  retirement_age?: number | null;
  claims_rent_credit?: boolean;
  lump_sum_pct?: number;
}

export interface Assumptions {
  id: number;
  plan_id: number;
  inflation_rate: number;
  default_growth_rate: number;
  property_growth_rate: number;
  earnings_growth: number;
  state_pension_age: number;
  state_pension_annual_amount: number;
  state_pension_escalation_rate: number;
}

export interface AssumptionsUpsert {
  inflation_rate: number;
  default_growth_rate: number;
  property_growth_rate: number;
  earnings_growth: number;
  state_pension_age: number;
  state_pension_annual_amount: number;
  state_pension_escalation_rate: number;
}

export type IncomeKind =
  | "employment"
  | "self_employment"
  | "rental"
  | "state_pension"
  | "private_pension_drawdown"
  | "annuity"
  | "other";

export interface IncomeSource {
  id: number;
  person_id: number;
  kind: IncomeKind;
  name: string;
  gross_amount: number;
  start_year: number;
  end_year: number | null;
  escalation_rate: number;
  pays_prsi: boolean;
  pays_usc: boolean;
  pension_contribution_pct: number;
  employer_pension_contribution_pct: number;
}

export interface IncomeSourceCreate {
  kind: IncomeKind;
  name: string;
  gross_amount: number;
  start_year: number;
  end_year?: number | null;
  escalation_rate?: number;
  pays_prsi?: boolean;
  pays_usc?: boolean;
  pension_contribution_pct?: number;
  employer_pension_contribution_pct?: number;
}

export type IncomeSourceUpdate = Partial<IncomeSourceCreate>;
export type ExpenseUpdate = Partial<ExpenseCreate>;
export type AssetUpdate = Partial<AssetCreate>;
export type LiabilityUpdate = Partial<LiabilityCreate>;
export type PersonUpdate = Partial<PersonCreate>;

export type ExpenseCategory = "basic" | "discretionary" | "single_year" | "legacy";

export interface Expense {
  id: number;
  plan_id: number;
  name: string;
  category: ExpenseCategory;
  amount: number;
  start_year: number;
  end_year: number | null;
  escalation_rate: number;
  owner_person_id: number | null;
}

export interface ExpenseCreate {
  name: string;
  category: ExpenseCategory;
  amount: number;
  start_year: number;
  end_year?: number | null;
  escalation_rate?: number;
  owner_person_id?: number | null;
}

export type AssetKind =
  | "cash"
  | "deposit"
  | "investment_unwrapped"
  | "etf_fund"
  | "prsa"
  | "occupational_pension"
  | "arf"
  | "property_primary"
  | "property_btl";

export interface Asset {
  id: number;
  plan_id: number;
  name: string;
  kind: AssetKind;
  value: number;
  growth_rate: number;
  owner_person_id: number | null;
  cost_basis: number;
  acquired_year: number | null;
  annual_contribution: number;
  contribution_pct_of_net_income: number;
  contribution_pct_of_gross_income: number;
  contribution_start_year: number | null;
  contribution_end_year: number | null;
  avc_annual: number;
  avc_pct_of_gross: number;
}

export interface AssetCreate {
  name: string;
  kind: AssetKind;
  value: number;
  growth_rate?: number;
  owner_person_id?: number | null;
  cost_basis?: number;
  acquired_year?: number | null;
  annual_contribution?: number;
  contribution_pct_of_net_income?: number;
  contribution_pct_of_gross_income?: number;
  contribution_start_year?: number | null;
  contribution_end_year?: number | null;
  avc_annual?: number;
  avc_pct_of_gross?: number;
}

export type LiabilityKind = "mortgage" | "loan";

export interface Liability {
  id: number;
  plan_id: number;
  name: string;
  kind: LiabilityKind;
  principal: number;
  interest_rate: number;
  term_months: number;
  start_year: number;
  monthly_payment: number;
}

export interface LiabilityCreate {
  name: string;
  kind: LiabilityKind;
  principal: number;
  interest_rate: number;
  term_months: number;
  start_year: number;
  monthly_payment?: number | null;
}

export type GoalKind =
  | "retirement"
  | "pre_retirement_spend"
  | "milestone"
  | "education"
  | "net_worth"
  | "gift";

export interface Goal {
  id: number;
  plan_id: number;
  kind: GoalKind;
  name: string;
  target_amount: number;
  target_year: number;
  linked_person_id: number | null;
  notes: string | null;
}

export interface GoalCreate {
  kind: GoalKind;
  name: string;
  target_amount: number;
  target_year: number;
  linked_person_id?: number | null;
  notes?: string | null;
}

export type GoalUpdate = Partial<GoalCreate>;

export interface PersonYear {
  person_id: number;
  name: string;
  age: number;
  gross_income: number;
  income_tax: number;
  usc: number;
  prsi: number;
  net_income: number;
}

export interface MonteCarloYearRow {
  year: number;
  p5: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
}

export interface MonteCarloResponse {
  runs: number;
  years: MonteCarloYearRow[];
  shortfall_probability: number;
  median_final_net_worth: number;
}

export type CatGroup = "A" | "B" | "C" | "exempt";

export interface Bequest {
  id: number;
  plan_id: number;
  from_person_id: number;
  to_person_id: number | null;
  cat_group: CatGroup;
  share_pct: number;
  notes: string | null;
}

export interface BequestCreate {
  from_person_id: number;
  to_person_id?: number | null;
  cat_group?: CatGroup;
  share_pct: number;
  notes?: string | null;
}

export type BequestUpdate = Partial<BequestCreate>;

export interface YearRow {
  year: number;
  ages: Record<number, number>;
  persons: PersonYear[];
  gross_income_total: number;
  income_by_kind: Record<string, number>;
  total_tax: number;
  income_tax: number;
  usc: number;
  prsi: number;
  net_income_total: number;
  expenses_total: number;
  expenses_by_category: Record<string, number>;
  surplus_or_shortfall: number;
  asset_balances: Record<number, number>;
  asset_balances_by_kind: Record<string, number>;
  withdrawals_by_asset: Record<number, number>;
  net_worth: number;
  accessible_net_worth: number;
  liability_balances: Record<number, number>;
  debt_outstanding: number;
  investment_tax: number;
  realised_gains: number;
  pension_contributions: number;
  employer_pension_contributions: number;
  pension_lump_sum: number;
  pension_lump_sum_tax: number;
  arf_drawdowns: number;
  state_pension_total: number;
  goal_status: Record<number, string>;
  notes: string[];
  cat_paid: number;
  estate_transfers: Record<number, number>;
  asset_contributions: number;
}

export interface ProjectionSummary {
  plan_id: number;
  base_year: number;
  projection_years: number;
  final_net_worth: number;
  peak_net_worth: number;
  peak_net_worth_year: number;
  first_shortfall_year: number | null;
  total_lifetime_tax: number;
}

export interface ProjectionResponse {
  summary: ProjectionSummary;
  years: YearRow[];
}

// Scenario overrides: keyed by entity bucket. Per-entity buckets map id→partial fields,
// and may also carry an `_added` list of new entities to inject (used to model promotions,
// one-off events, windfalls etc that don't exist in the base plan).
// `assumptions` is a flat partial dict — singleton per plan.
export type AddedIncome = IncomeSourceCreate & { person_id: number };
export type AddedExpense = ExpenseCreate;

export type BucketPatch<TPatch, TAdded> = Record<string, TPatch> & { _added?: TAdded[] };

export type ScenarioOverrides = {
  people?: Record<string, Partial<PersonCreate>>;
  incomes?: BucketPatch<Partial<IncomeSourceCreate>, AddedIncome>;
  expenses?: BucketPatch<Partial<ExpenseCreate>, AddedExpense>;
  assets?: Record<string, Partial<AssetCreate>>;
  liabilities?: Record<string, Partial<LiabilityCreate>>;
  goals?: Record<string, Partial<GoalCreate>>;
  assumptions?: Partial<AssumptionsUpsert>;
};

export interface Scenario {
  id: number;
  plan_id: number;
  name: string;
  parent_scenario_id: number | null;
  overrides: ScenarioOverrides;
}

export interface ScenarioCreate {
  name: string;
  parent_scenario_id?: number | null;
  overrides?: ScenarioOverrides;
}

export interface ScenarioUpdate {
  name?: string;
  parent_scenario_id?: number | null;
  overrides?: ScenarioOverrides;
}

export interface CompareSide {
  scenario_id: number | null;
  scenario_name: string;
  projection: ProjectionResponse;
}

export interface CompareDeltaRow {
  year: number;
  net_worth_delta: number;
  net_income_delta: number;
  total_tax_delta: number;
  expenses_delta: number;
}

export interface CompareResponse {
  a: CompareSide;
  b: CompareSide;
  delta: CompareDeltaRow[];
}

export type PlanRole = "viewer" | "editor" | "owner";

export interface PlanMember {
  user_id: number;
  role: PlanRole;
  email: string | null;
  display_name: string | null;
  created_at: string;
}

export interface PlanInvite {
  id: number;
  plan_id: number;
  role: PlanRole;
  token: string;
  email: string | null;
  created_at: string;
  expires_at: string | null;
  accepted_at: string | null;
  accepted_by_user_id: number | null;
}

export interface PlanInvitePreview {
  plan_id: number;
  plan_name: string;
  role: PlanRole;
  email_bound: boolean;
  inviter_display_name: string | null;
  expires_at: string | null;
}
