import { apiFetch } from './client'

export type InventoryItem = { product_id: number; sku: string; name: string; category: string; cost_price: string; sale_price: string; quantity_on_hand: string; quantity_reserved: string; quantity_available: string; low_stock: boolean }
export type StockMovement = { id: number; product_id: number; product_name: string; order_id: number | null; quantity_delta: string; reason: string; note: string | null; created_at: string }
export type SerializedUnit = { id: number; product_id: number; product_name: string; serial_number: string; status: string; received_at: string | null }
export type Dispatch = { id: number; order_id: number; dispatch_number: string; status: string; dispatched_at: string | null; delivered_at: string | null; items: { id: number; order_item_id: number; product_id: number; product_name: string; quantity: string; serialized_unit_id: number | null }[] }
export type DispatchListItem = { id: number; order_id: number; dispatch_number: string; status: string; dispatched_at: string | null }
export const getInventory = (params: { low_stock?: boolean; search?: string } = {}) => { const query = new URLSearchParams(); if (params.low_stock) query.set('low_stock', 'true'); if (params.search) query.set('search', params.search); return apiFetch<InventoryItem[]>(`/inventory${query.size ? `?${query}` : ''}`) }
export const getStockMovements = (product_id?: number) => apiFetch<StockMovement[]>(`/inventory/movements${product_id ? `?product_id=${product_id}` : ''}`)
export const getSerializedUnit = (serial: string) => apiFetch<SerializedUnit>(`/inventory/serialized-units/${encodeURIComponent(serial)}`)
export const getDispatch = (id: number) => apiFetch<Dispatch>(`/inventory/dispatches/${id}`)
export const getDispatches = () => apiFetch<DispatchListItem[]>('/inventory/dispatches')
