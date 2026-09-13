import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { DemandLine } from './types'

export function useDemand(filters?: { project?: string; portfolio?: string }) {
  const params = new URLSearchParams()
  if (filters?.project) params.set('project', filters.project)
  if (filters?.portfolio) params.set('portfolio', filters.portfolio)
  const qs = params.toString()
  return useQuery({
    queryKey: ['demand', filters?.project ?? null, filters?.portfolio ?? null],
    queryFn: () => api.get<DemandLine[]>(`/demand${qs ? `?${qs}` : ''}`),
    refetchInterval: 30_000,
  })
}

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<string[]>('/projects'),
  })
}

export function usePortfolios() {
  return useQuery({
    queryKey: ['portfolios'],
    queryFn: () => api.get<string[]>('/portfolios'),
  })
}

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: () => api.get<string[]>('/roles'),
  })
}

function useInvalidateDemand() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['demand'] })
    qc.invalidateQueries({ queryKey: ['projects'] })
    qc.invalidateQueries({ queryKey: ['portfolios'] })
    qc.invalidateQueries({ queryKey: ['roles'] })
  }
}

export function useCreateDemand() {
  const invalidate = useInvalidateDemand()
  return useMutation({
    mutationFn: (data: {
      project: string
      portfolio?: string
      role: string
      fte: number
      start_date: string
      end_date: string
      note?: string
    }) => api.post<DemandLine>('/demand', data),
    onSuccess: invalidate,
  })
}

export function useUpdateDemand() {
  const invalidate = useInvalidateDemand()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Omit<DemandLine, 'id' | 'created_at'>> }) =>
      api.put<DemandLine>(`/demand/${id}`, data),
    onSuccess: invalidate,
  })
}

export function useDeleteDemand() {
  const invalidate = useInvalidateDemand()
  return useMutation({
    mutationFn: (id: string) => api.del(`/demand/${id}`),
    onSuccess: invalidate,
  })
}
