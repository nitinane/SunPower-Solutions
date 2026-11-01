import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { sendCopilotMessage, type CopilotMessage } from '../../api/copilot'

const suggestions = [
  'How many customers and orders are in the ERP?',
  'Summarize installation job statuses.',
  'Which product has sold the most units?',
  'How many support tickets are open?',
]

export function CopilotPage() {
  const [messages, setMessages] = useState<CopilotMessage[]>([])
  const [draft, setDraft] = useState('')
  const [provider, setProvider] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // This effect intentionally has no cleanup return value.
    if (bottom.current) bottom.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, provider])

  const mutation = useMutation({
    mutationFn: ({ prompt, history }: { prompt: string; history: CopilotMessage[] }) => sendCopilotMessage(prompt, history.slice(-8)),
    onSuccess: result => { setMessages(current => [...current, { role: 'assistant', content: result.answer }]); setProvider(result.provider) },
    onError: error => setMessages(current => [...current, { role: 'assistant', content: error instanceof ApiError ? error.message : error.message || 'Copilot is unavailable. Please try again.' }]),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    const prompt = draft.trim()
    if (!prompt || mutation.isPending) return
    const history = messages
    setMessages(current => [...current, { role: 'user', content: prompt }])
    setDraft('')
    mutation.mutate({ prompt, history })
  }

  return <div className="copilot-page">
    <header className="copilot-header"><div><span className="copilot-eyebrow">SUNPOWER SOLUTIONS</span><h1>AI Copilot</h1><p>Ask questions about live ERP operations and financial summaries.</p></div><span className="copilot-model"><i />{provider || 'Qwen local · Groq fallback'}</span></header>
    <section className="copilot-chat" aria-label="AI Copilot conversation">
      <div className="copilot-transcript" aria-live="polite">
        {!messages.length && <div className="copilot-welcome"><span className="copilot-spark">✦</span><h2>How can I help?</h2><p>I search a small, relevant set of live ERP records for each question. Data visibility follows your role.</p><div className="copilot-suggestions">{suggestions.map(prompt => <button key={prompt} onClick={() => setDraft(prompt)}>{prompt}<span aria-hidden="true">↗</span></button>)}</div></div>}
        {messages.map((message, index) => <article className={`copilot-message ${message.role}`} key={`${index}-${message.role}`}><div className="copilot-avatar">{message.role === 'user' ? 'You' : '✦'}</div><div className="copilot-bubble"><span>{message.role === 'user' ? 'You' : 'Copilot'}</span><p>{message.content}</p></div></article>)}
        {mutation.isPending && <article className="copilot-message assistant"><div className="copilot-avatar">✦</div><div className="copilot-bubble"><span>Copilot</span><p className="copilot-thinking"><i/><i/><i/> Checking local ERP data…</p></div></article>}
        <div ref={bottom}/>
      </div>
      <form className="copilot-composer" onSubmit={submit}><textarea value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="Ask about customers, jobs, inventory, tickets…" maxLength={2000} rows={2} aria-label="Message Copilot"/><div className="copilot-compose-footer"><small>Enter to send · Shift + Enter for a new line</small><button type="submit" disabled={!draft.trim() || mutation.isPending} aria-label="Send message"><span className="material-symbols-outlined">arrow_upward</span></button></div></form>
      <p className="copilot-disclaimer">Demo assistant. Verify important figures in the ERP reports.</p>
    </section>
  </div>
}
