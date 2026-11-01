import { apiFetch } from './client'
import type { Page_ProductRead_ } from '../pages/field/contracts'
export const products = (query = '') => apiFetch<Page_ProductRead_>(`/products${query}`)
