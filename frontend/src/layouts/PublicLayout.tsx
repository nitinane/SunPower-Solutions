import { Outlet } from 'react-router-dom'
import { SharedSidebar } from '../components/SharedSidebar'
export function PublicLayout() { return <div className="shared-layout"><SharedSidebar /><main className="shared-layout-content"><Outlet /></main></div> }
