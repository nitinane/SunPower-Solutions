import { apiFetch } from './client'
import type { TicketRead } from '../pages/field/contracts'
export const ticket = (id: number, query = '') => apiFetch<TicketRead>(`/tickets/${id}${query}`)
export const createTicket = (body?: unknown) => apiFetch<TicketRead>(`/tickets`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const assignTicket = (id: number, body?: unknown) => apiFetch<TicketRead>(`/tickets/${id}/assign`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const resolveTicket = (id: number, body?: unknown) => apiFetch<TicketRead>(`/tickets/${id}/resolve`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const replaceUnit = (id: number, body?: unknown) => apiFetch<TicketRead>(`/tickets/${id}/replace-unit`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
export const confirmTicket = (id: number, body?: unknown) => apiFetch<TicketRead>(`/tickets/${id}/confirm`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
