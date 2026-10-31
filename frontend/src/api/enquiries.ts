import { apiFetch } from './client'

export type EnquiryStatus = 'new' | 'contacted' | 'qualified' | 'unqualified' | 'closed'
export type Enquiry = {
  id: number; customer_id: number | null; site_id: number | null; contact_name: string; phone_raw: string
  phone_e164: string | null; email: string | null; source: string; status: EnquiryStatus; notes: string | null
  address_line: string; city: string; state: string; pincode: string; requested_capacity_kw: string
  system_type: string; customer_type: string; subsidy_requested: boolean; shadow_free_roof_area_sqft: string | null
  monthly_bill_amount: string | null; grid_connection_suitable: boolean | null; assigned_to: number | null
  qualified_by: number | null; qualified_at: string | null; close_reason: string | null; is_overdue: boolean
  created_at: string; updated_at: string
}
export type Page<T> = { items: T[]; total: number; page: number; page_size: number }
export type EnquiryCreate = Omit<Enquiry, 'id' | 'customer_id' | 'site_id' | 'phone_raw' | 'phone_e164' | 'status' | 'shadow_free_roof_area_sqft' | 'monthly_bill_amount' | 'grid_connection_suitable' | 'assigned_to' | 'qualified_by' | 'qualified_at' | 'close_reason' | 'is_overdue' | 'created_at' | 'updated_at'> & { phone: string }
export type PublicEnquiryCreate = Omit<EnquiryCreate, 'source'> & { website_url: '' }
export type EnquiryReceipt = { reference: string; message: string }
export type AuditEntry = { id: number; action: string; actor_user_id: number | null; actor_name: string | null; old_data: Record<string, unknown> | null; new_data: Record<string, unknown> | null; created_at: string }
export type StaffBrief = { id: number; full_name: string; role: string; phone: string | null }

function params(values: Record<string, string | number | boolean | undefined>) {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== '') query.append(key, String(value)) })
  return query.size ? `?${query}` : ''
}
export const getEnquiries = (filters: { status?: string; source?: string; assigned?: string; overdue?: boolean; search?: string; page?: number; page_size?: number } = {}) => apiFetch<Page<Enquiry>>(`/enquiries${params(filters)}`)
export const createEnquiry = (body: EnquiryCreate, idempotencyKey: string) => apiFetch<Enquiry>('/enquiries', { method: 'POST', headers: { 'idempotency-key': idempotencyKey }, body: JSON.stringify(body) })
export const createPublicEnquiry = (body: PublicEnquiryCreate, idempotencyKey: string) => apiFetch<EnquiryReceipt>('/enquiries/public', { method: 'POST', headers: { 'idempotency-key': idempotencyKey }, body: JSON.stringify(body) })
export const getEnquiry = (id: number) => apiFetch<Enquiry>(`/enquiries/${id}`)
export const assignEnquiry = (id: number, user_id: number) => apiFetch<Enquiry>(`/enquiries/${id}/assign`, { method: 'POST', body: JSON.stringify({ user_id }) })
export const qualifyEnquiry = (id: number, body: { outcome: 'qualified' | 'unqualified' | 'contacted'; shadow_free_roof_area_sqft?: string; monthly_bill_amount?: string; grid_connection_suitable?: boolean; notes?: string }) => apiFetch<Enquiry>(`/enquiries/${id}/qualification`, { method: 'POST', body: JSON.stringify(body) })
export const closeEnquiry = (id: number, reason: string) => apiFetch<Enquiry>(`/enquiries/${id}/close`, { method: 'POST', body: JSON.stringify({ reason }) })
export const getEnquiryHistory = (id: number) => apiFetch<AuditEntry[]>(`/enquiries/${id}/history`)
export const getStaff = (roles: string[]) => { const query = new URLSearchParams(); roles.forEach(role => query.append('role', role)); return apiFetch<StaffBrief[]>(`/users${query.size ? `?${query}` : ''}`) }
