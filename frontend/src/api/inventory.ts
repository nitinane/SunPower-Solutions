import { apiFetch } from './client'
import type { Page } from './enquiries'

export type StockRow = { product_id: number; sku: string; name: string; category: string; requires_serial: boolean; on_hand: string; low_stock: boolean }
export type Product = { id: number; sku: string; name: string; category: string; sale_price: string; gst_percent: string; in_stock: string; requires_serial: boolean }
export type Receipt = { id: number; receipt_number: string; supplier_name: string; supplier_invoice_ref: string; received_on: string; created_by: number | null; created_at: string; total: string; lines: { id: number; product_id: number; sku: string; name: string; qty: string; unit_cost: string; line_total: string }[] }
export type DispatchSummary = { id: number; dispatch_number: string; order_id: number; order_number: string; customer: { id: number; name: string; phone: string; email: string | null }; site: { id: number; address_line1: string; address_line2: string | null; city: string; state: string; pincode: string }; status: string; dispatched_at: string | null; delivered_at: string | null; receiver_name: string | null; created_at: string }
export type Dispatch = DispatchSummary & { lines: { order_item_id: number; sku: string; name: string; qty: string; requires_serial: boolean; scanned: number; serials: { serial_number: string; serialized_unit_id: number }[] }[] }
const pageQuery = (page: number, page_size: number) => `page=${page}&page_size=${page_size}`
export const getStock = (page = 1, page_size = 100) => apiFetch<Page<StockRow>>(`/stock?${pageQuery(page, page_size)}`)
export const getProducts = (filters: { search?: string; requires_serial?: boolean; page?: number; page_size?: number } = {}) => { const q = new URLSearchParams(); Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') q.set(k, String(v)) }); return apiFetch<Page<Product>>(`/products${q.size ? `?${q}` : ''}`) }
export const getReceipts = (page = 1, page_size = 50) => apiFetch<Page<Receipt>>(`/stock/receipts?${pageQuery(page, page_size)}`)
export const getReceipt = (id: number) => apiFetch<Receipt>(`/stock/receipts/${id}`)
export const getDispatches = (page = 1, page_size = 50) => apiFetch<Page<DispatchSummary>>(`/dispatches?${pageQuery(page, page_size)}`)
export const getDispatch = (id: number) => apiFetch<Dispatch>(`/dispatches/${id}`)
