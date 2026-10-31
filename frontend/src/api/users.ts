import { apiFetch } from './client'
import { getCurrentUser } from './auth'

export type User = { id: number; full_name: string; role: string; phone: string | null }
export { getCurrentUser }
export const getUsers = (role?: string) => apiFetch<User[]>(`/users${role ? `?role=${encodeURIComponent(role)}` : ''}`)
export const getUser = (id: number) => apiFetch<User>(`/users/${id}`)
