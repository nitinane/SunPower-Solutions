import { apiFetch } from './client'
import type { SurveyRead } from '../pages/field/contracts'
export const survey = (id: number, query = '') => apiFetch<SurveyRead>(`/surveys/${id}${query}`)
export const submitSurvey = (id: number, body?: unknown) => apiFetch<SurveyRead>(`/surveys/${id}/submit`, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
