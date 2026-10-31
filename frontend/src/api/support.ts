import { apiFetch } from './client'
import type { SupportResult } from '../pages/field/contracts'
export const searchCustomers = (query = '') => apiFetch<SupportResult[]>(`/support/search${query}`)
