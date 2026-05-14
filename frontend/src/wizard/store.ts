import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import type {
  AssetCreate,
  ExpenseCreate,
  FilingStatus,
  GoalCreate,
  IncomeSourceCreate,
  LiabilityCreate,
  PersonCreate,
  PlanCreate,
} from "../api/types";

export type WizardStepId =
  | "plan"
  | "people"
  | "income"
  | "assets"
  | "properties"
  | "liabilities"
  | "expenses"
  | "goals"
  | "review";

export const WIZARD_STEPS: WizardStepId[] = [
  "plan",
  "people",
  "income",
  "assets",
  "properties",
  "liabilities",
  "expenses",
  "goals",
  "review",
];

export type DraftId = string;

function newDraftId(): DraftId {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `d_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export interface PlanDraft extends PlanCreate {}

export interface PersonDraft extends PersonCreate {
  draftId: DraftId;
}

export interface IncomeDraft extends IncomeSourceCreate {
  draftId: DraftId;
  personDraftId: DraftId;
  isBonus?: boolean;
}

export interface AssetDraft extends AssetCreate {
  draftId: DraftId;
  ownerPersonDraftId?: DraftId | null;
}

export interface LiabilityDraft extends LiabilityCreate {
  draftId: DraftId;
  linkedPropertyDraftId?: DraftId | null;
}

export interface ExpenseDraft extends ExpenseCreate {
  draftId: DraftId;
  ownerPersonDraftId?: DraftId | null;
}

export interface GoalDraft extends GoalCreate {
  draftId: DraftId;
  linkedPersonDraftId?: DraftId | null;
}

export interface WizardState {
  plan: PlanDraft;
  people: PersonDraft[];
  incomes: IncomeDraft[];
  assets: AssetDraft[];
  properties: AssetDraft[];
  liabilities: LiabilityDraft[];
  expenses: ExpenseDraft[];
  goals: GoalDraft[];
  currentStep: WizardStepId;
  dirty: boolean;

  setPlan: (p: Partial<PlanDraft>) => void;

  addPerson: (p: Omit<PersonDraft, "draftId">) => DraftId;
  updatePerson: (id: DraftId, p: Partial<PersonDraft>) => void;
  removePerson: (id: DraftId) => void;

  addIncome: (i: Omit<IncomeDraft, "draftId">) => DraftId;
  updateIncome: (id: DraftId, i: Partial<IncomeDraft>) => void;
  removeIncome: (id: DraftId) => void;

  addAsset: (a: Omit<AssetDraft, "draftId">) => DraftId;
  updateAsset: (id: DraftId, a: Partial<AssetDraft>) => void;
  removeAsset: (id: DraftId) => void;

  addProperty: (a: Omit<AssetDraft, "draftId">) => DraftId;
  updateProperty: (id: DraftId, a: Partial<AssetDraft>) => void;
  removeProperty: (id: DraftId) => void;

  addLiability: (l: Omit<LiabilityDraft, "draftId">) => DraftId;
  updateLiability: (id: DraftId, l: Partial<LiabilityDraft>) => void;
  removeLiability: (id: DraftId) => void;

  addExpense: (e: Omit<ExpenseDraft, "draftId">) => DraftId;
  updateExpense: (id: DraftId, e: Partial<ExpenseDraft>) => void;
  removeExpense: (id: DraftId) => void;

  addGoal: (g: Omit<GoalDraft, "draftId">) => DraftId;
  updateGoal: (id: DraftId, g: Partial<GoalDraft>) => void;
  removeGoal: (id: DraftId) => void;

  goTo: (step: WizardStepId) => void;
  reset: () => void;
}

const defaultPlan = (): PlanDraft => ({
  name: "",
  base_year: new Date().getFullYear(),
  projection_years: 40,
  filing_status: "single" as FilingStatus,
});

const initialState = (): Pick<
  WizardState,
  | "plan"
  | "people"
  | "incomes"
  | "assets"
  | "properties"
  | "liabilities"
  | "expenses"
  | "goals"
  | "currentStep"
  | "dirty"
> => ({
  plan: defaultPlan(),
  people: [],
  incomes: [],
  assets: [],
  properties: [],
  liabilities: [],
  expenses: [],
  goals: [],
  currentStep: "plan",
  dirty: false,
});

export const useWizard = create<WizardState>()(
  persist(
    (set) => ({
      ...initialState(),

      setPlan: (p) =>
        set((s) => ({ plan: { ...s.plan, ...p }, dirty: true })),

      addPerson: (p) => {
        const draftId = newDraftId();
        set((s) => ({ people: [...s.people, { ...p, draftId }], dirty: true }));
        return draftId;
      },
      updatePerson: (id, p) =>
        set((s) => ({
          people: s.people.map((x) => (x.draftId === id ? { ...x, ...p } : x)),
          dirty: true,
        })),
      removePerson: (id) =>
        set((s) => ({
          people: s.people.filter((x) => x.draftId !== id),
          incomes: s.incomes.filter((i) => i.personDraftId !== id),
          assets: s.assets.map((a) =>
            a.ownerPersonDraftId === id ? { ...a, ownerPersonDraftId: null } : a,
          ),
          properties: s.properties.map((a) =>
            a.ownerPersonDraftId === id ? { ...a, ownerPersonDraftId: null } : a,
          ),
          goals: s.goals.map((g) =>
            g.linkedPersonDraftId === id ? { ...g, linkedPersonDraftId: null } : g,
          ),
          dirty: true,
        })),

      addIncome: (i) => {
        const draftId = newDraftId();
        set((s) => ({ incomes: [...s.incomes, { ...i, draftId }], dirty: true }));
        return draftId;
      },
      updateIncome: (id, i) =>
        set((s) => ({
          incomes: s.incomes.map((x) => (x.draftId === id ? { ...x, ...i } : x)),
          dirty: true,
        })),
      removeIncome: (id) =>
        set((s) => ({
          incomes: s.incomes.filter((x) => x.draftId !== id),
          dirty: true,
        })),

      addAsset: (a) => {
        const draftId = newDraftId();
        set((s) => ({ assets: [...s.assets, { ...a, draftId }], dirty: true }));
        return draftId;
      },
      updateAsset: (id, a) =>
        set((s) => ({
          assets: s.assets.map((x) => (x.draftId === id ? { ...x, ...a } : x)),
          dirty: true,
        })),
      removeAsset: (id) =>
        set((s) => ({ assets: s.assets.filter((x) => x.draftId !== id), dirty: true })),

      addProperty: (a) => {
        const draftId = newDraftId();
        set((s) => ({ properties: [...s.properties, { ...a, draftId }], dirty: true }));
        return draftId;
      },
      updateProperty: (id, a) =>
        set((s) => ({
          properties: s.properties.map((x) => (x.draftId === id ? { ...x, ...a } : x)),
          dirty: true,
        })),
      removeProperty: (id) =>
        set((s) => ({
          properties: s.properties.filter((x) => x.draftId !== id),
          liabilities: s.liabilities.map((l) =>
            l.linkedPropertyDraftId === id ? { ...l, linkedPropertyDraftId: null } : l,
          ),
          dirty: true,
        })),

      addLiability: (l) => {
        const draftId = newDraftId();
        set((s) => ({ liabilities: [...s.liabilities, { ...l, draftId }], dirty: true }));
        return draftId;
      },
      updateLiability: (id, l) =>
        set((s) => ({
          liabilities: s.liabilities.map((x) => (x.draftId === id ? { ...x, ...l } : x)),
          dirty: true,
        })),
      removeLiability: (id) =>
        set((s) => ({
          liabilities: s.liabilities.filter((x) => x.draftId !== id),
          dirty: true,
        })),

      addExpense: (e) => {
        const draftId = newDraftId();
        set((s) => ({ expenses: [...s.expenses, { ...e, draftId }], dirty: true }));
        return draftId;
      },
      updateExpense: (id, e) =>
        set((s) => ({
          expenses: s.expenses.map((x) => (x.draftId === id ? { ...x, ...e } : x)),
          dirty: true,
        })),
      removeExpense: (id) =>
        set((s) => ({ expenses: s.expenses.filter((x) => x.draftId !== id), dirty: true })),

      addGoal: (g) => {
        const draftId = newDraftId();
        set((s) => ({ goals: [...s.goals, { ...g, draftId }], dirty: true }));
        return draftId;
      },
      updateGoal: (id, g) =>
        set((s) => ({
          goals: s.goals.map((x) => (x.draftId === id ? { ...x, ...g } : x)),
          dirty: true,
        })),
      removeGoal: (id) =>
        set((s) => ({ goals: s.goals.filter((x) => x.draftId !== id), dirty: true })),

      goTo: (step) => set({ currentStep: step }),
      reset: () => set(initialState()),
    }),
    {
      name: "meridian:wizard:v1",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        plan: s.plan,
        people: s.people,
        incomes: s.incomes,
        assets: s.assets,
        properties: s.properties,
        liabilities: s.liabilities,
        expenses: s.expenses,
        goals: s.goals,
      }),
      version: 1,
    },
  ),
);
