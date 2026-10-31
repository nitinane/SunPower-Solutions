import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

type ActiveSection = 'dashboard' | 'tech' | 'warehouse' | 'customers' | 'installations' | 'inventory' | 'reports' | 'settings'

function Icon({ children }: { children: string }) {
  return <span className="material-symbols-outlined" aria-hidden="true">{children}</span>
}

export function SharedSidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const operations = [['groups', 'Customers', 'customers'], ['wb_sunny', 'Installations', 'installations'], ['warehouse', 'Inventory', 'inventory'], ['monitoring', 'Reports', 'reports'], ['settings', 'Settings', 'settings']] as const
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
      <div className="shared-workspace-pills shared-sidebar-text" aria-label="Switch workspace"><button aria-current={location.pathname === '/' ? 'page' : undefined} className={location.pathname === '/' ? 'active' : ''} onClick={() => navigate('/')}><span>Owner</span></button><button aria-current={location.pathname === '/technician' ? 'page' : undefined} className={location.pathname === '/technician' ? 'active' : ''} onClick={() => navigate('/technician')}><span>Tech</span></button><button aria-current={location.pathname === '/warehouse' ? 'page' : undefined} className={location.pathname === '/warehouse' ? 'active' : ''} onClick={() => navigate('/warehouse')}><span>Warehouse</span></button></div>
      <nav className="shared-nav">
        <button className="shared-ai-button" title="AI Copilot" aria-label="AI Copilot" onClick={() => navigate('/')}><Icon>auto_awesome</Icon><span className="shared-sidebar-text">AI Copilot</span><b className="shared-sidebar-text">AI LIVE</b></button>
        <span className="shared-section shared-sidebar-text">WORKSPACES</span>
        <button title="Owner Dashboard" aria-label="Owner Dashboard" aria-current={selected('dashboard') ? 'page' : undefined} className={`shared-nav-button ${selected('dashboard') ? 'selected' : ''}`} onClick={() => navigate('/')}><Icon>dashboard</Icon><span className="shared-sidebar-text">Owner Dashboard</span><small className="shared-sidebar-text">Live</small></button>
        <button title="Technician Workspace" aria-label="Technician Workspace" aria-current={selected('tech') ? 'page' : undefined} className={`shared-nav-button ${selected('tech') ? 'selected' : ''}`} onClick={() => navigate('/technician')}><Icon>engineering</Icon><span className="shared-sidebar-text">Technician Workspace</span><small className="shared-sidebar-text">Field</small></button>
        <button title="Warehouse Workspace" aria-label="Warehouse Workspace" aria-current={selected('warehouse') ? 'page' : undefined} className={`shared-nav-button ${selected('warehouse') ? 'selected' : ''}`} onClick={() => navigate('/warehouse')}><Icon>inventory_2</Icon><span className="shared-sidebar-text">Warehouse Workspace</span><small className="shared-sidebar-text">BOM</small></button>
        <span className="shared-divider" />
        <span className="shared-section shared-sidebar-text">OPERATIONS</span>
        {operations.map(([icon, label, path]) => <button key={path} title={label} aria-label={label} aria-current={selected(path) ? 'page' : undefined} className={`shared-nav-button ${selected(path) ? 'selected' : ''}`} onClick={() => navigate(`/${path}`)}><Icon>{icon}</Icon><span className="shared-sidebar-text">{label}</span></button>)}
      </nav>
    </div>
    <div className="shared-sidebar-bottom"><span className="shared-sidebar-text">v4.2</span><button title={collapsed ? 'Expand menu' : 'Collapse menu'} aria-label={collapsed ? 'Expand navigation menu' : 'Collapse navigation menu'} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}><span className="shared-sidebar-text">{collapsed ? 'Expand Menu' : 'Collapse Menu'}</span><Icon>{collapsed ? 'keyboard_double_arrow_right' : 'keyboard_double_arrow_left'}</Icon></button></div>
  </aside>
}
