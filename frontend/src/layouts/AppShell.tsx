import { Outlet } from 'react-router-dom'
import { SharedSidebar } from '../components/SharedSidebar'

export function AppShell() {
  return <div className="app-shell shared-app-shell"><SharedSidebar /><main className="shared-app-content"><Outlet /></main></div>
}
