import { apiFetch } from './client'

export type CurrentUser = { id: number; full_name: string; email: string; phone: string | null; role: string }
export type LoginResponse = { user: CurrentUser; expires_at: string }
export const login = (email: string, password: string) => apiFetch<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
export const getCurrentUser = () => apiFetch<CurrentUser>('/auth/me')
export const logout = () => apiFetch<void>('/auth/logout', { method: 'POST' })
