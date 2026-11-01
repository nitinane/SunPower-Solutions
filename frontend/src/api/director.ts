import { apiFetch } from './client'
import type { Page } from './enquiries'
import type { Survey } from './sales'

export type DashboardSummary = { period: 'today' | 'week' | 'month'; from_at: string; to_at: string; cards: { new_enquiries: number; orders_confirmed: number; payments_received: string; advance_payments: string; technician_hours: string; profit: string; stock_purchases: string; unfinished_jobs: number; open_repairs: number }; profit_per_job: { order_number: string; customer: string; system_kw: string; revenue: string; material_cost: string; labour_cost: string; warranty_service_cost: string; profit: string; margin_percent: string }[]; unfinished_jobs: { order_number: string; customer: string; stage: string; days_open: number }[]; open_repairs: { ticket_number: string; customer: string; under_warranty: boolean; status: string; days_open: number }[] }
export type Share = { id: number; period: string; expires_at: string; created_at: string }
export type PayRunSummary = { id: number; month: string; status: string; paid_on: string | null; payment_reference: string | null; technician_count: number; total_amount: string }
export type PayRun = PayRunSummary & { lines: { technician_id: number; technician_name: string; install_hours: string; repair_hours: string; rate: string; install_amount: string; repair_amount: string; amount: string; jobs: unknown[]; tickets: unknown[] }[] }
export const getDashboardSummary = (period: 'today' | 'week' | 'month' = 'month', sort: 'recent' | 'profit_asc' = 'recent') => apiFetch<DashboardSummary>(`/dashboard/summary?period=${period}&sort=${sort}`)
export type DashboardTrendPoint = { month: string; booked_order_value: string; payments_received: string }
export const getDashboardTrend = (months = 12) => apiFetch<DashboardTrendPoint[]>(`/dashboard/trend?months=${months}`)
export const getShares = (page = 1, page_size = 20) => apiFetch<Page<Share>>(`/dashboard/share?page=${page}&page_size=${page_size}`)
export const createShare = (period: 'today' | 'week' | 'month', expires_in_hours: number) => apiFetch<{ id: number; url: string; expires_at: string }>('/dashboard/share', { method: 'POST', body: JSON.stringify({ period, expires_in_hours }) })
export const revokeShare = (id: number) => apiFetch<void>(`/dashboard/share/${id}`, { method: 'DELETE' })
export const getDirectorSurveys = (status = 'submitted', page = 1, page_size = 20) => apiFetch<Page<Survey>>(`/surveys?status=${encodeURIComponent(status)}&page=${page}&page_size=${page_size}`)
export const approveSurvey = (id: number) => apiFetch<Survey>(`/surveys/${id}/approve`, { method: 'POST' })
export const rejectSurvey = (id: number, reason: string) => apiFetch<Survey>(`/surveys/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) })
export const getPayRuns = (page = 1, page_size = 20) => apiFetch<Page<PayRunSummary>>(`/pay-runs?page=${page}&page_size=${page_size}`)
export const getPayRun = (id: number) => apiFetch<PayRun>(`/pay-runs/${id}`)
export const createPayRun = (month: string) => apiFetch<PayRun>('/pay-runs', { method: 'POST', body: JSON.stringify({ month }) })
export const markPayRunPaid = (id: number, paid_on: string, payment_reference: string) => apiFetch<PayRun>(`/pay-runs/${id}/mark-paid`, { method: 'POST', body: JSON.stringify({ paid_on, payment_reference }) })
