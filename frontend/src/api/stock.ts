import { apiFetch } from './client'
import type { Page_ReceiptRead_, Page_StockRow_, ReceiptRead } from '../pages/field/contracts'
export const stock = (query = '') => apiFetch<Page_StockRow_>(`/stock${query}`)
export const receipts = (query = '') => apiFetch<Page_ReceiptRead_>(`/stock/receipts${query}`)
export const receiveStock = (body?: unknown) => apiFetch<ReceiptRead>(`/stock/receipts`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
