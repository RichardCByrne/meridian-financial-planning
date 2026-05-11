import { useQueries } from "@tanstack/react-query";

import { api } from "../api/client";
import type { IncomeSource, Person } from "../api/types";

export function useIncomeForPeople(people: Person[]): { incomes: IncomeSource[]; isLoading: boolean } {
  const queries = useQueries({
    queries: people.map((p) => ({
      queryKey: ["person", p.id, "income"],
      queryFn: () => api.get<IncomeSource[]>(`/people/${p.id}/income`),
      enabled: Number.isFinite(p.id),
    })),
  });
  const isLoading = queries.some((q) => q.isLoading);
  const incomes = queries.flatMap((q) => q.data ?? []);
  return { incomes, isLoading };
}
