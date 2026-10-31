import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getCurrentUser } from '../api/auth'

type NavItem = { icon: string; label: string; path: string; badge?: string }
function Icon({ children }: { children: string }) { return <span className="material-symbols-outlined" aria-hidden="true">{children}</span> }
function canSee(role: string | undefined, allowed: string[]) { return !!role && (role === 'admin' || allowed.includes(role)) }
function pathSelected(pathname: string, path: string) { return pathname === path || pathname.startsWith(`${path}/`) }

export function SharedSidebar() {
  const location = useLocation(); const navigate = useNavigate(); const [collapsed, setCollapsed] = useState(false)
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false }); const role = session.data?.role
  const workspaces: NavItem[] = [{ icon: 'dashboard', label: 'Owner Dashboard', path: '/' }, { icon: 'engineering', label: 'Technician Demo', path: '/technician', badge: 'Demo' }, { icon: 'inventory_2', label: 'Warehouse Demo', path: '/warehouse', badge: 'Demo' }]
  const realWorkspaces: NavItem[] = []
  if (canSee(role, ['office'])) realWorkspaces.push({ icon: 'support_agent', label: 'Office Sales', path: '/office/enquiries' })
  if (canSee(role, ['director'])) realWorkspaces.push({ icon: 'query_stats', label: 'Director', path: '/director/overview' })
  if (canSee(role, ['technician'])) {
    realWorkspaces.push({ icon: 'today', label: 'My Day', path: '/technician/today' })
  }
  if (canSee(role, ['warehouse'])) {
    realWorkspaces.push({ icon: 'move_to_inbox', label: 'Receiving', path: '/warehouse/receiving' })
    realWorkspaces.push({ icon: 'local_shipping', label: 'Dispatches', path: '/warehouse/dispatches' })
  }
  if (canSee(role, ['manager'])) {
    realWorkspaces.push({ icon: 'calendar_month', label: 'Crew Schedule', path: '/manager/schedule' })
    realWorkspaces.push({ icon: 'fact_check', label: 'Survey Review', path: '/manager/surveys' })
  }
  if (canSee(role, ['support'])) realWorkspaces.push({ icon: 'support', label: 'Support', path: '/support' })
  const operations: NavItem[] = []
  if (canSee(role, ['office', 'support'])) operations.push({ icon: 'groups', label: 'Customers', path: '/customers' })
  if (canSee(role, ['office', 'manager'])) operations.push({ icon: 'wb_sunny', label: 'Installations', path: '/installations' })
  if (canSee(role, ['office', 'warehouse'])) operations.push({ icon: 'warehouse', label: 'Inventory', path: '/inventory' })
  if (canSee(role, ['director'])) operations.push({ icon: 'monitoring', label: 'Reports', path: '/reports' })
  if (canSee(role, ['director', 'manager', 'office', 'support', 'warehouse'])) operations.push({ icon: 'settings', label: 'Settings', path: '/settings' })
  const selected = (item: NavItem) => item.path === '/' ? location.pathname === '/' : item.badge ? location.pathname === item.path : pathSelected(location.pathname, item.path)
  const renderItem = (item: NavItem) => <Link key={item.path} to={item.path} title={item.label} aria-label={item.label} aria-current={selected(item) ? 'page' : undefined} className={`shared-nav-button ${selected(item) ? 'selected' : ''}`}><Icon>{item.icon}</Icon><span className="shared-sidebar-text">{item.label}</span>{item.badge && <small className="shared-sidebar-text">{item.badge}</small>}</Link>
  return <aside className={`shared-sidebar ${collapsed ? 'shared-sidebar-collapsed' : ''}`} aria-label="Main navigation">
    <div className="shared-sidebar-main">
      <Link to="/" className="shared-brand"><span><Icon>solar_power</Icon></span><b className="shared-sidebar-text">SunPower<small>SOLUTIONS ERP</small></b></Link>
      <div className="shared-workspace-pills shared-sidebar-text" aria-label="Switch demo workspace"><button aria-current={location.pathname === '/' ? 'page' : undefined} className={location.pathname === '/' ? 'active' : ''} onClick={() => navigate('/')}><span>Owner</span></button><button aria-current={location.pathname === '/technician' ? 'page' : undefined} className={location.pathname === '/technician' ? 'active' : ''} onClick={() => navigate('/technician')}><span>Tech</span></button><button aria-current={location.pathname === '/warehouse' ? 'page' : undefined} className={location.pathname === '/warehouse' ? 'active' : ''} onClick={() => navigate('/warehouse')}><span>Warehouse</span></button></div>
      <nav className="shared-nav">
        <button className="shared-ai-button" title="AI Copilot" aria-label="AI Copilot" onClick={() => navigate('/')}><Icon>auto_awesome</Icon><span className="shared-sidebar-text">AI Copilot</span><b className="shared-sidebar-text">AI LIVE</b></button>
        <span className="shared-section shared-sidebar-text">WORKSPACES</span>{workspaces.map(renderItem)}
        {realWorkspaces.length > 0 && <><span className="shared-section shared-sidebar-text">MY WORK</span>{realWorkspaces.map(renderItem)}</>}
        {operations.length > 0 && <><span className="shared-divider"/><span className="shared-section shared-sidebar-text">OPERATIONS</span>{operations.map(renderItem)}</>}
      </nav>
    </div>
    <div className="shared-sidebar-bottom"><span className="shared-sidebar-text">v4.2</span><button title={collapsed ? 'Expand menu' : 'Collapse menu'} aria-label={collapsed ? 'Expand navigation menu' : 'Collapse navigation menu'} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}><span className="shared-sidebar-text">{collapsed ? 'Expand Menu' : 'Collapse Menu'}</span><Icon>{collapsed ? 'keyboard_double_arrow_right' : 'keyboard_double_arrow_left'}</Icon></button></div>
  </aside>
}
