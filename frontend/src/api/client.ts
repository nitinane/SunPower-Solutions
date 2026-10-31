const API_BASE = '/api/v1'
export class ApiError extends Error { constructor(public status: number, message: string, public fields: Record<string, string> = {}) { super(message) } }
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) {
    let message = response.statusText
    let fields: Record<string, string> = {}
    try { const body = await response.json(); message = body.error?.message ?? body.detail ?? message; fields = body.error?.fields ?? {} } catch { /* use status text */ }
    throw new ApiError(response.status, message, fields)
  }
  if (response.status === 204 || response.headers.get('content-length') === '0') return undefined as T
  return response.json() as Promise<T>
}
