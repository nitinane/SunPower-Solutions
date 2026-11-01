import { apiFetch, ApiError } from './client'

export type Installation = { id: number; order_id: number; order_number: string; customer_id: number; customer_name: string; site_id: number; site_name: string | null; city: string; status: string; scheduled_at: string | null; started_at: string | null; completed_at: string | null; completion_notes: string | null; installed_capacity_kw: string | null; power_test_passed: boolean | null; signed_by_name: string | null; signed_at: string | null; technicians: { id: number; technician_id: number; full_name: string; hours_worked: string; hourly_rate: string }[]; evidence: { id: number; evidence_type: string; content_type: string; file_size_bytes: number; caption: string | null; captured_at: string | null }[] }
export function getInstallations(params: { status?: string; scheduled_from?: string; scheduled_to?: string } = {}) { const query = new URLSearchParams(); for (const [key, value] of Object.entries(params)) if (value) query.set(key, value); return apiFetch<Installation[]>(`/installations${query.size ? `?${query}` : ''}`) }
export function getInstallation(id: number) { return apiFetch<Installation>(`/installations/${id}`) }
export function evidenceUrl(jobId: number, evidenceId: number) { return `/api/v1/installations/${jobId}/evidence/${evidenceId}` }
export async function getEvidence(jobId: number, evidenceId: number) {
  const response = await fetch(evidenceUrl(jobId, evidenceId), { credentials: 'include' })
  if (!response.ok) throw new ApiError(response.status, 'Could not retrieve installation evidence')
  return response.blob()
}
