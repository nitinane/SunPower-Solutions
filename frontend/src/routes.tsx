import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { HomePage } from './App'
import { PublicLayout } from './layouts/PublicLayout'
import { StaffLayout } from './layouts/StaffLayout'
import { PublicPage } from './pages/public/PublicPage'
import { OfficePage } from './pages/office/OfficePage'
import { SupportPage } from './pages/support/SupportPage'
import { DirectorPage } from './pages/director/DirectorPage'
import { CustomerDetailPage, LoginPage, OperationsPage } from './pages/operations/OperationsPage'

function RoleGuard() { return <Outlet /> }
export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { element: <RoleGuard />, children: [
    { path: '/login', element: <LoginPage /> },
    { path: '/public', element: <PublicLayout />, children: [{ index: true, element: <PublicPage /> }] },
    { path: '/office', element: <StaffLayout />, children: [{ index: true, element: <OfficePage /> }] },
    { path: '/warehouse', element: <HomePage initialWorkspace="warehouse" /> },
    { path: '/technician', element: <HomePage initialWorkspace="tech" /> },
    { path: '/support', element: <StaffLayout />, children: [{ index: true, element: <SupportPage /> }] },
    { path: '/director', element: <StaffLayout />, children: [{ index: true, element: <DirectorPage /> }] },
    { path: '/customers', element: <OperationsPage module="customers" /> },
    { path: '/customers/:id', element: <CustomerDetailPage /> },
    { path: '/installations', element: <OperationsPage module="installations" /> },
    { path: '/inventory', element: <OperationsPage module="inventory" /> },
    { path: '/reports', element: <OperationsPage module="reports" /> },
    { path: '/settings', element: <OperationsPage module="settings" /> },
  ] },
  { path: '*', element: <Navigate to="/" replace /> },
])
