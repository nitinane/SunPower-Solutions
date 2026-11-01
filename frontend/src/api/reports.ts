import { apiFetch } from './client'

export type Report = { customer_count: number; order_count: number; total_revenue: string; outstanding_payments: string; installation_count: number; completed_jobs: number; unfinished_jobs: number; open_support_tickets: number; profit_per_job: Record<string, string> }
export const getReport = () => apiFetch<Report>('/dashboard/reports')
export const getDashboardSummary = () => apiFetch<Report>('/dashboard/summary')
