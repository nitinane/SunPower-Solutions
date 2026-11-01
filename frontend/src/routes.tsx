import { useQuery } from '@tanstack/react-query'
import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { getCurrentUser } from './api/auth'
import type { CurrentUser } from './api/auth'
import { ApiError } from './api/client'
import { PublicLayout } from './layouts/PublicLayout'
import { StaffLayout } from './layouts/StaffLayout'
import { PublicPage } from './pages/public/PublicPage'
import { DirectorPage } from './pages/director/DirectorPage'
import { CustomerDetailPage, LoginPage, OperationsPage } from './pages/operations/OperationsPage'
import { CopilotPage } from './pages/copilot/CopilotPage'

const landingPath: Record<string, string> = {
  admin: '/director',
  director: '/director',
  office: '/customers',
  warehouse: '/inventory',
  technician: '/installations',
  support: '/customers',
}

function SessionGate({ roles, children }: { roles: string[]; children: ReactNode }) {
  const location = useLocation()
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false })
  if (session.isPending) return <main className="route-state" aria-live="polite"><span className="ops-spinner"/><p>Verifying your SunPower account…</p></main>
  if (session.isError && session.error instanceof ApiError && session.error.status === 401) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  }
  if (session.isError) return <main className="route-state"><h1>Could not verify your account</h1><p>{session.error.message}</p><button onClick={() => void session.refetch()}>Try again</button></main>
  const user = session.data as CurrentUser
  if (!roles.includes(user.role) && user.role !== 'admin') {
    return <main className="route-state"><h1>Access restricted</h1><p>Your {user.role} account cannot access this page.</p><a href={landingPath[user.role] ?? '/login'}>Go to your workspace</a></main>
  }
  return children
}

function Protected({ roles, children }: { roles: string[]; children: ReactNode }) {
  return <SessionGate roles={roles}>{children}</SessionGate>
}

function RoleHome() {
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false })
  if (session.isPending) return <main className="route-state" aria-live="polite"><span className="ops-spinner"/><p>Verifying your SunPower account…</p></main>
  if (session.isError && session.error instanceof ApiError && session.error.status === 401) return <Navigate to="/login" replace />
  if (session.isError) return <main className="route-state"><h1>Could not verify your account</h1><p>{session.error.message}</p><button onClick={() => void session.refetch()}>Try again</button></main>
  const destination = landingPath[session.data.role]
  if (!destination) return <main className="route-state"><h1>No workspace is configured</h1><p>Your {session.data.role} account has no dashboard in this frontend.</p></main>
  return <Navigate to={destination} replace />
}

function RoleGuard() { return <Outlet /> }

export const router = createBrowserRouter([
  { path: '/', element: <RoleHome /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/public', element: <PublicLayout />, children: [{ index: true, element: <PublicPage /> }] },
  { path: '/office', element: <Protected roles={['director', 'office']}><Navigate to="/customers" replace /></Protected> },
  { path: '/support', element: <Protected roles={['director', 'support']}><Navigate to="/customers" replace /></Protected> },
  { path: '/director', element: <Protected roles={['director']}><StaffLayout /></Protected>, children: [{ index: true, element: <DirectorPage /> }] },
  { path: '/warehouse', element: <Protected roles={['director', 'warehouse']}><Navigate to="/inventory" replace /></Protected> },
  { path: '/technician', element: <Protected roles={['director', 'technician']}><Navigate to="/installations" replace /></Protected> },
  { element: <RoleGuard />, children: [
    { path: '/copilot', element: <Protected roles={['director', 'office', 'warehouse', 'technician', 'surveyor', 'support']}><StaffLayout /></Protected>, children: [{ index: true, element: <CopilotPage /> }] },
    { path: '/customers', element: <Protected roles={['director', 'office', 'support']}><OperationsPage module="customers" /></Protected> },
    { path: '/customers/:id', element: <Protected roles={['director', 'office', 'support']}><CustomerDetailPage /></Protected> },
    { path: '/installations', element: <Protected roles={['director', 'office', 'technician']}><OperationsPage module="installations" /></Protected> },
    { path: '/inventory', element: <Protected roles={['director', 'warehouse']}><OperationsPage module="inventory" /></Protected> },
    { path: '/reports', element: <Protected roles={['director']}><OperationsPage module="reports" /></Protected> },
    { path: '/settings', element: <Protected roles={['director', 'office', 'warehouse', 'technician', 'surveyor', 'support']}><OperationsPage module="settings" /></Protected> },
  ] },
  { path: '*', element: <Navigate to="/" replace /> },
])
