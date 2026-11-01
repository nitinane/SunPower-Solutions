import { apiFetch } from './client'
import { getCurrentUser } from './auth'

export type User = { id: number; full_name: string; email: string; phone: string | null; role: string; hourly_rate: string | null; is_active: boolean; created_at: string; updated_at: string }
export { getCurrentUser }
export const getUsers = (role?: string) => apiFetch<User[]>(`/users${role ? `?role=${encodeURIComponent(role)}` : ''}`)
export const getUser = (id: number) => apiFetch<User>(`/users/${id}`)
