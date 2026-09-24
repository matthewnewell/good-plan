import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { CostKind, FunctionsResponse, Plan, ProjectsResponse, RatesResponse, Wbs } from './types'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<ProjectsResponse>('/projects'),
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ status: string; ai_configured: boolean }>('/health'),
    staleTime: 60_000,
  })
}

export function useRates() {
  return useQuery({
    queryKey: ['rates'],
    queryFn: () => api.get<RatesResponse>('/rates'),
    staleTime: 60_000,
  })
}

export function useFunctions() {
  return useQuery({
    queryKey: ['functions'],
    queryFn: () => api.get<FunctionsResponse>('/functions'),
    staleTime: 60_000,
  })
}

export function usePlan(planId: string | undefined) {
  return useQuery({
    queryKey: ['plan', planId],
    queryFn: () => api.get<Plan>(`/plans/${planId}`),
    enabled: !!planId,
  })
}

/** Every plan endpoint returns the whole recomputed plan, so a mutation just drops that straight
 * into the cache — no refetch, and the grid, totals and chart all update from one response. */
function usePlanMutation<V>(planId: string | undefined, fn: (vars: V) => Promise<Plan>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (plan) => {
      qc.setQueryData(['plan', planId], plan)
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useCreatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (depotProjectId: string) => api.post<Plan>('/plans', { depot_project_id: depotProjectId }),
    onSuccess: (plan) => {
      qc.setQueryData(['plan', plan.id], plan)
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useUpdatePlan(planId: string | undefined) {
  return usePlanMutation(planId, (data: Partial<Pick<Plan, 'contract_value' | 'contract_type' | 'include_burden' | 'fee_percent' | 'award_fee_percent' | 'hours_per_fte_week' | 'week_count'>>) =>
    api.put<Plan>(`/plans/${planId}`, data),
  )
}

export function useAddLine(planId: string | undefined) {
  return usePlanMutation(planId, (data: { category: string; wbs?: string }) =>
    api.post<Plan>(`/plans/${planId}/lines`, data),
  )
}

export function useUpdateLine(planId: string | undefined) {
  return usePlanMutation(
    planId,
    ({ id, ...data }: { id: string; category?: string; wbs?: string | null; rate_override?: number | null; note?: string | null }) =>
      api.put<Plan>(`/lines/${id}`, data),
  )
}

export function useDeleteLine(planId: string | undefined) {
  return usePlanMutation(planId, (lineId: string) => api.del<Plan>(`/lines/${lineId}`))
}

export function useSetWeeks(planId: string | undefined) {
  return usePlanMutation(planId, ({ lineId, weeks }: { lineId: string; weeks: Record<string, number> }) =>
    api.put<Plan>(`/lines/${lineId}/weeks`, { weeks }),
  )
}

export function useSpread(planId: string | undefined) {
  return usePlanMutation(planId, ({ lineId, ...data }: { lineId: string; fte: number; start: string; end: string }) =>
    api.post<Plan>(`/lines/${lineId}/spread`, data),
  )
}

export function useAddCost(planId: string | undefined) {
  return usePlanMutation(planId, (data: { kind: CostKind }) => api.post<Plan>(`/plans/${planId}/costs`, data))
}

export function useUpdateCost(planId: string | undefined) {
  return usePlanMutation(
    planId,
    ({ id, ...data }: { id: string; description?: string; vendor?: string; wbs?: string; qty?: number; unit_cost?: number; need_date?: string | null; detail?: string | null }) =>
      api.put<Plan>(`/costs/${id}`, data),
  )
}

export function useDeleteCost(planId: string | undefined) {
  return usePlanMutation(planId, (costId: string) => api.del<Plan>(`/costs/${costId}`))
}

// ── WBS ───────────────────────────────────────────────────────────────────────────────────────

export function useWbs(planId: string | undefined) {
  return useQuery({
    queryKey: ['wbs', planId],
    queryFn: () => api.get<Wbs>(`/plans/${planId}/wbs`),
    enabled: !!planId,
    staleTime: 30_000,
  })
}

function useWbsMutation<V>(planId: string | undefined, fn: (vars: V) => Promise<Wbs>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (wbs) => qc.setQueryData(['wbs', planId], wbs),
  })
}

export function useAddWbsElement(planId: string | undefined) {
  return useWbsMutation(planId, (data: { title: string; parent_code?: string }) => api.post<Wbs>(`/plans/${planId}/wbs`, data))
}

export function useRenameWbsElement(planId: string | undefined) {
  return useWbsMutation(planId, ({ id, title }: { id: string; title: string }) => api.put<Wbs>(`/plans/${planId}/wbs/${id}`, { title }))
}

export function useDeleteWbsElement(planId: string | undefined) {
  return useWbsMutation(planId, (id: string) => api.del<Wbs>(`/plans/${planId}/wbs/${id}`))
}

export function usePromoteWbs(planId: string | undefined) {
  return useWbsMutation(planId, (author: string | undefined) => api.post<Wbs>(`/plans/${planId}/wbs/promote`, { author }))
}

export function useSetPhases(planId: string | undefined) {
  return usePlanMutation(planId, ({ costId, phases }: { costId: string; phases: { date: string; percent: number }[] }) =>
    api.put<Plan>(`/costs/${costId}/phases`, { phases }),
  )
}
