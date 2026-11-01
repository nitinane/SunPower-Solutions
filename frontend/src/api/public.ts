import { apiFetch } from './client'
import type { DashboardSummary } from './director'

export const getSharedDashboard = (token: string) => apiFetch<DashboardSummary>(`/public/dashboard/${encodeURIComponent(token)}`)
