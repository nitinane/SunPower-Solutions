const API_BASE = '/api/v1'
export class ApiError extends Error { constructor(public status: number, message: string) { super(message) } }
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('access_token')
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!response.ok) {
    let message = response.statusText
    try { const body = await response.json(); message = body.error?.message ?? body.detail ?? message } catch { /* use status text */ }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}
