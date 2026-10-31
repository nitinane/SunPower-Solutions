import { apiFetch } from './client'
import type { JobRead } from '../pages/field/contracts'
export const job = (id: number, query = '') => apiFetch<JobRead>(`/installation-jobs/${id}${query}`)
export const startJob = (id: number, body?: unknown) => apiFetch<JobRead>(`/installation-jobs/${id}/start`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const completeJob = (id: number, body?: unknown) => apiFetch<JobRead>(`/installation-jobs/${id}/complete`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
