import { ApiError } from './client'
import { apiFetch } from './client'
import type { Page } from './enquiries'

export type CrewMember = { user_id: number; name: string; hours: string | null }
export type ScheduleRow = { job_id: number; status: string; scheduled_date: string | null; order_id: number; order_number: string; customer_name: string; customer_phone: string; site: { id: number; address_line1: string; address_line2: string | null; city: string; state: string; pincode: string }; crew: CrewMember[] }
export type InstallationJob = { id: number; status: string; order_id: number; order_number: string; customer_name: string; customer_phone: string; site: ScheduleRow['site']; scheduled_date: string | null; started_at: string | null; finished_at: string | null; system_kw: string | null; power_test_passed: boolean | null; signer_name: string | null; crew: CrewMember[]; lines: { order_item_id: number; sku: string; name: string; qty: string; requires_serial: boolean; serials: string[] }[]; photo_ids: number[]; signature_id: number | null }
export type Evidence = { id: number; job_id: number; kind: string; content_type: string; size_bytes: number; created_at: string }
export function getSchedule(params: { from: string; to: string; page?: number; page_size?: number }) { const query = new URLSearchParams({ from: params.from, to: params.to, page: String(params.page ?? 1), page_size: String(params.page_size ?? 50) }); return apiFetch<Page<ScheduleRow>>(`/schedule?${query}`) }
export function getInstallation(id: number) { return apiFetch<InstallationJob>(`/installation-jobs/${id}`) }
export function evidenceUrl(evidenceId: number) { return `/api/v1/evidence/${evidenceId}/file` }
export async function getEvidence(evidenceId: number) { const response = await fetch(evidenceUrl(evidenceId), { credentials: 'include' }); if (!response.ok) throw new ApiError(response.status, 'Could not retrieve installation evidence'); return response.blob() }
