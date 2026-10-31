import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'
import { HomePage } from './App'
import { PublicLayout } from './layouts/PublicLayout'
import { StaffLayout } from './layouts/StaffLayout'
import { MobileLayout } from './layouts/MobileLayout'
import { PublicPage } from './pages/public/PublicPage'
import { OfficePage } from './pages/office/OfficePage'
import { WarehousePage } from './pages/warehouse/WarehousePage'
import { TechnicianPage } from './pages/technician/TechnicianPage'
import { SupportPage } from './pages/support/SupportPage'
import { DirectorPage } from './pages/director/DirectorPage'

function RoleGuard() { return <Outlet /> }
export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { element: <RoleGuard />, children: [
    { path: '/public', element: <PublicLayout />, children: [{ index: true, element: <PublicPage /> }] },
    { path: '/office', element: <StaffLayout />, children: [{ index: true, element: <OfficePage /> }] },
    { path: '/warehouse', element: <StaffLayout />, children: [{ index: true, element: <WarehousePage /> }] },
    { path: '/technician', element: <MobileLayout />, children: [{ index: true, element: <TechnicianPage /> }] },
    { path: '/support', element: <StaffLayout />, children: [{ index: true, element: <SupportPage /> }] },
    { path: '/director', element: <StaffLayout />, children: [{ index: true, element: <DirectorPage /> }] },
  ] },
  { path: '*', element: <Navigate to="/" replace /> },
])
