import { useQuery } from '@tanstack/react-query'
import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { HomePage } from './App'
import { getCurrentUser } from './api/auth'
import type { CurrentUser } from './api/auth'
import { PublicLayout } from './layouts/PublicLayout'
import { StaffLayout } from './layouts/StaffLayout'
import { PublicPage } from './pages/public/PublicPage'
import { SharedDashboardPage } from './pages/public/SharedDashboardPage'
import { OfficePage } from './pages/office/OfficePage'
import { SupportPage } from './pages/support/SupportPage'
import { DirectorPage } from './pages/director/DirectorPage'
import { LoginPage, OperationsPage } from './pages/operations/OperationsPage'
import { fieldRoutes } from './routes.field'

function SessionGate({ roles, children }: { roles: string[]; children: ReactNode }) {
  const location = useLocation()
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false })
  if (session.isPending) return <main className="route-state"><span className="spinner"/><p>Checking your staff session…</p></main>
  if (session.isError && 'status' in session.error && session.error.status === 401) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  if (session.isError) return <main className="route-state"><h1>Could not verify your session</h1><p>{session.error.message}</p><button onClick={() => void session.refetch()}>Try again</button></main>
  const user = session.data as CurrentUser
  if (!roles.includes(user.role) && user.role !== 'admin') return <main className="route-state"><h1>Access restricted</h1><p>Your {user.role} account does not have access to this section.</p><button onClick={() => window.history.back()}>Go back</button></main>
  return children
}

function ProtectedStaffLayout({ roles }: { roles: string[] }) { return <SessionGate roles={roles}><StaffLayout /></SessionGate> }
function RoleGuard() { return <Outlet /> }
export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/technician', element: <HomePage initialWorkspace="tech" /> },
  { path: '/warehouse', element: <HomePage initialWorkspace="warehouse" /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/public', element: <PublicLayout />, children: [{ index: true, element: <PublicPage /> }] },
  { path: '/share/:token', element: <PublicLayout />, children: [{ index: true, element: <SharedDashboardPage /> }] },
  { path: '/office', element: <ProtectedStaffLayout roles={['director', 'office']} />, children: [{ index: true, element: <Navigate to="enquiries" replace /> }, { path: ':tab', element: <OfficePage /> }] },
  { path: '/director', element: <ProtectedStaffLayout roles={['director']} />, children: [{ index: true, element: <Navigate to="overview" replace /> }, { path: ':tab', element: <DirectorPage /> }] },
  { element: <RoleGuard />, children: [
    { path: '/support', element: <ProtectedStaffLayout roles={['director', 'support']} />, children: [{ index: true, element: <SupportPage /> }] },
    { path: '/customers', element: <SessionGate roles={['director', 'office', 'support']}><OperationsPage module="customers" /></SessionGate> },
    { path: '/installations', element: <SessionGate roles={['director', 'manager', 'office']}><OperationsPage module="installations" /></SessionGate> },
    { path: '/inventory', element: <SessionGate roles={['director', 'office', 'warehouse']}><OperationsPage module="inventory" /></SessionGate> },
    { path: '/reports', element: <SessionGate roles={['director']}><OperationsPage module="reports" /></SessionGate> },
    { path: '/settings', element: <SessionGate roles={['director', 'manager', 'office', 'support', 'warehouse']}><OperationsPage module="settings" /></SessionGate> },
  ] },
  ...fieldRoutes,
  { path: '*', element: <Navigate to="/" replace /> },
])
