import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUser } from '../api/auth'

type ActiveSection = 'dashboard' | 'tech' | 'warehouse' | 'customers' | 'installations' | 'inventory' | 'reports' | 'settings'

function Icon({ children }: { children: string }) {
  return <span className="material-symbols-outlined" aria-hidden="true">{children}</span>
}

export function SharedSidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false })
  const role = session.data?.role
  const access: Record<string, string[]> = {
    admin: ['customers', 'installations', 'inventory', 'reports', 'settings'],
    director: ['customers', 'installations', 'inventory', 'reports', 'settings'],
    office: ['customers', 'installations', 'settings'],
    warehouse: ['inventory', 'settings'],
    technician: ['installations', 'settings'],
    surveyor: ['settings'],
    support: ['customers', 'settings'],
  }
  const operations = ([['groups', 'Customers', 'customers'], ['wb_sunny', 'Installations', 'installations'], ['warehouse', 'Inventory', 'inventory'], ['monitoring', 'Reports', 'reports'], ['settings', 'Settings', 'settings']] as const).filter(([, , path]) => access[role ?? '']?.includes(path))
  // The URL is the single source of truth. Component-local workspace state can
  // survive route changes and otherwise leave two items highlighted at once.
  const selected = (section: ActiveSection) => {
    if (section === 'dashboard') return location.pathname === '/' || location.pathname === '/director'
    if (section === 'tech') return location.pathname === '/technician'
    if (section === 'warehouse') return location.pathname === '/warehouse'
    return location.pathname === `/${section}` || location.pathname.startsWith(`/${section}/`)
  }

  return <aside className={`shared-sidebar ${collapsed ? 'shared-sidebar-collapsed' : ''}`} aria-label="Main navigation">
    <div className="shared-sidebar-main">
      <Link to="/" className="shared-brand"><span><Icon>solar_power</Icon></span><b className="shared-sidebar-text">SunPower<small>SOLUTIONS ERP</small></b></Link>
      <div className="shared-workspace-pills shared-sidebar-text" aria-label="Your workspace">{role === 'director' || role === 'admin' ? <button className="active" onClick={() => navigate('/director')}><span>Owner</span></button> : role === 'technician' ? <button className="active" onClick={() => navigate('/technician')}><span>Tech</span></button> : role === 'warehouse' ? <button className="active" onClick={() => navigate('/warehouse')}><span>Warehouse</span></button> : role === 'office' ? <button className="active" onClick={() => navigate('/customers')}><span>Office</span></button> : role === 'support' ? <button className="active" onClick={() => navigate('/customers')}><span>Support</span></button> : null}</div>
      <nav className="shared-nav">
        <button className="shared-ai-button" title="AI Copilot" aria-label="AI Copilot" aria-current={location.pathname === '/copilot' ? 'page' : undefined} onClick={() => navigate('/copilot')}><Icon>auto_awesome</Icon><span className="shared-sidebar-text">AI Copilot</span><b className="shared-sidebar-text">AI</b></button>
        {(role === 'director' || role === 'admin' || role === 'technician' || role === 'warehouse' || role === 'office' || role === 'support') && <>
          <span className="shared-section shared-sidebar-text">WORKSPACE</span>
          {role === 'director' || role === 'admin' ? <button title="Director Dashboard" aria-label="Director Dashboard" aria-current={selected('dashboard') ? 'page' : undefined} className={`shared-nav-button ${selected('dashboard') ? 'selected' : ''}`} onClick={() => navigate('/director')}><Icon>dashboard</Icon><span className="shared-sidebar-text">Director Dashboard</span><small className="shared-sidebar-text">Live</small></button> : null}
          {role === 'technician' ? <button title="Technician Workspace" aria-label="Technician Workspace" aria-current={selected('tech') ? 'page' : undefined} className={`shared-nav-button ${selected('tech') ? 'selected' : ''}`} onClick={() => navigate('/technician')}><Icon>engineering</Icon><span className="shared-sidebar-text">My Field Work</span><small className="shared-sidebar-text">Assigned</small></button> : null}
          {role === 'warehouse' ? <button title="Warehouse Workspace" aria-label="Warehouse Workspace" aria-current={selected('warehouse') ? 'page' : undefined} className={`shared-nav-button ${selected('warehouse') ? 'selected' : ''}`} onClick={() => navigate('/warehouse')}><Icon>inventory_2</Icon><span className="shared-sidebar-text">Warehouse</span><small className="shared-sidebar-text">Stock</small></button> : null}
          {role === 'office' ? <button title="Office Customer Desk" aria-label="Office Customer Desk" className={`shared-nav-button ${selected('customers') ? 'selected' : ''}`} onClick={() => navigate('/customers')}><Icon>support_agent</Icon><span className="shared-sidebar-text">Customer Desk</span></button> : null}
          {role === 'support' ? <button title="Support Customer Search" aria-label="Support Customer Search" className={`shared-nav-button ${selected('customers') ? 'selected' : ''}`} onClick={() => navigate('/customers')}><Icon>support_agent</Icon><span className="shared-sidebar-text">Customer Search</span></button> : null}
          <span className="shared-divider" />
        </>}
        <span className="shared-section shared-sidebar-text">OPERATIONS</span>
        {operations.map(([icon, label, path]) => <button key={path} title={label} aria-label={label} aria-current={selected(path) ? 'page' : undefined} className={`shared-nav-button ${selected(path) ? 'selected' : ''}`} onClick={() => navigate(`/${path}`)}><Icon>{icon}</Icon><span className="shared-sidebar-text">{label}</span></button>)}
      </nav>
    </div>
    <div className="shared-sidebar-bottom"><span className="shared-sidebar-text">v4.2</span><button title={collapsed ? 'Expand menu' : 'Collapse menu'} aria-label={collapsed ? 'Expand navigation menu' : 'Collapse navigation menu'} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}><span className="shared-sidebar-text">{collapsed ? 'Expand Menu' : 'Collapse Menu'}</span><Icon>{collapsed ? 'keyboard_double_arrow_right' : 'keyboard_double_arrow_left'}</Icon></button></div>
  </aside>
}
