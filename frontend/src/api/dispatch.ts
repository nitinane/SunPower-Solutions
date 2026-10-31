import { apiFetch } from './client'
import type { DeliveryRead, DispatchRead, Page_DispatchRead_ } from '../pages/field/contracts'
export const dispatches = (query = '') => apiFetch<Page_DispatchRead_>(`/dispatches${query}`)
export const dispatch = (id: number, query = '') => apiFetch<DispatchRead>(`/dispatches/${id}${query}`)
export const scan = (id: number, body?: unknown) => apiFetch<DispatchRead>(`/dispatches/${id}/scan`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const send = (id: number, body?: unknown) => apiFetch<DispatchRead>(`/dispatches/${id}/send`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const deliver = (id: number, body?: unknown) => apiFetch<DeliveryRead>(`/dispatches/${id}/deliver`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
