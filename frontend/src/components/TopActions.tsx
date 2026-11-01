import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueries, useQuery } from '@tanstack/react-query'
import { getCurrentUser } from '../api/auth'
import { apiFetch } from '../api/client'
import { canOpen, screensFor, childScreens } from '../navigation'

type Alert = { label: string; path: string; requests: string[] }
export function TopActions() {
  const [panel, setPanel] = useState<'alerts' | 'help' | null>(null)
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false })
  const role = session.isError ? undefined : session.data?.role
  const alerts: Alert[] = []
  if (role && ['admin', 'director', 'manager', 'office', 'support', 'technician'].includes(role)) {
    alerts.push({ label: 'Open tickets', path: role === 'technician' ? '/technician/today' : role === 'manager' ? '/manager/schedule' : role === 'office' ? '/office/repairs' : '/support', requests: ['open', 'assigned', 'in_progress', 'waiting_customer', 'resolved'].map(status => `/tickets?status=${status}&page_size=1${role === 'technician' ? '&assigned_to_me=true' : ''}`) })
  }
  if (role && ['admin', 'director', 'manager'].includes(role)) alerts.push({ label: 'Unscheduled jobs', path: role === 'technician' ? '/technician/today' : role === 'manager' ? '/manager/schedule' : '/installations', requests: ['/installation-jobs?status=planned&page_size=1'] })
  if (canOpen(role, '/director')) alerts.push({ label: 'Surveys waiting for approval', path: '/director/surveys', requests: ['/surveys?status=submitted&page_size=1'] })
  if (canOpen(role, '/warehouse/dispatches')) alerts.push({ label: 'Pick lists waiting', path: '/warehouse/dispatches', requests: ['/dispatches?status=draft&page_size=1', '/dispatches?status=packed&page_size=1'] })
  const counts = useQueries({ queries: alerts.map(alert => ({ queryKey: ['navigation-alert', role, alert.label], queryFn: async () => {
    const pages = await Promise.all(alert.requests.map(path => apiFetch<{ total: number }>(path)))
    return pages.reduce((sum, page) => sum + page.total, 0)
  }, refetchInterval: 30000 })) })
  const today = useQuery({ queryKey: ['navigation-today'], queryFn: () => apiFetch<{ ticket_visits: unknown[]; installation_jobs: unknown[]; surveys: unknown[] }>('/me/today'), enabled: role === 'technician', refetchInterval: 30000 })
  const screens = screensFor(role)
  const scan = role === 'warehouse' ? '/warehouse/dispatches' : '/support?focus=search'
  return <div className="top-actions">
    {(!role || role === 'warehouse' || canOpen(role, '/support')) && <Link className="action-button" to={scan}><span className="material-symbols-outlined" aria-hidden="true">qr_code_scanner</span>Quick Scan</Link>}
    <div className="top-panel-anchor"><button aria-label="Notifications" aria-expanded={panel === 'alerts'} onClick={() => setPanel(panel === 'alerts' ? null : 'alerts')}><span className="material-symbols-outlined" aria-hidden="true">notifications</span></button>
      {panel === 'alerts' && <section className="top-popover" aria-label="Operational notifications"><h2>Notifications</h2>{!role && <Link to="/login">Sign in to see notifications</Link>}{alerts.map((alert, i) => <Link key={alert.label} to={alert.path}>{alert.label}: {counts[i].isPending ? 'Loading…' : counts[i].isError ? 'Unavailable' : counts[i].data}</Link>)}{role === 'technician' && <Link to="/technician/today">My day: {today.isPending ? 'Loading…' : today.isError ? 'Unavailable' : `${today.data.surveys.length} surveys, ${today.data.installation_jobs.length} jobs, ${today.data.ticket_visits.length} repair visits`}</Link>}{role && !alerts.length && role !== 'technician' && <p>No notification queues for this role.</p>}{counts.some(count => count.isError) && <button onClick={() => counts.forEach(count => void count.refetch())}>Retry counts</button>}</section>}
    </div>
    <div className="top-panel-anchor"><button aria-label="Help" aria-expanded={panel === 'help'} onClick={() => setPanel(panel === 'help' ? null : 'help')}><span className="material-symbols-outlined" aria-hidden="true">help</span></button>{panel === 'help' && <section className="top-popover" aria-label="Your screens"><h2>Your screens</h2>{screens.map(screen => <Link key={screen.path} to={screen.path}>{screen.label}</Link>)}{screens.flatMap(screen => (childScreens[screen.path] ?? []).map(([path, label]) => <Link key={path} to={path}>{label}</Link>))}{!role && <Link to="/login">Sign in</Link>}</section>}</div>
    <div className="user"><div><strong>{session.data?.full_name ?? 'Guest'}</strong><small>{role ?? 'Signed out'}</small></div></div>
  </div>
}
