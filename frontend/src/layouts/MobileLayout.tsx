import { Outlet } from 'react-router-dom'
import { SharedSidebar } from '../components/SharedSidebar'
export function MobileLayout() { return <div className="shared-layout"><SharedSidebar /><main className="shared-layout-content"><Outlet /></main></div> }
