import { apiFetch } from './client'

export type CopilotMessage = { role: 'user' | 'assistant'; content: string }
export type CopilotReply = { answer: string; provider: string }
export const sendCopilotMessage = (message: string, history: CopilotMessage[]) =>
  apiFetch<CopilotReply>('/copilot/chat', { method: 'POST', body: JSON.stringify({ message, history }) })
