import { ApiError } from '../api/client'
import { screensFor, childScreens, type NavItem } from '../navigation'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCurrentUser, logout } from '../api/auth'

function Icon({ children }: { children: string }) { return <span className="material-symbols-outlined" aria-hidden="true">{children}</span> }
function pathSelected(pathname: string, path: string) { return pathname === path || pathname.startsWith(`${path}/`) }

export function SharedSidebar() {
  const queryClient = useQueryClient()
  const signOut = useMutation({ mutationFn: logout, onSuccess: () => { queryClient.clear(); navigate('/login', { replace: true }) }, onError: error => { if (error instanceof ApiError && error.status === 401) { queryClient.clear(); navigate('/login', { replace: true }) } } })
  const location = useLocation(); const navigate = useNavigate(); const [collapsed, setCollapsed] = useState(false)
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false }); const role = session.isError ? undefined : session.data?.role
  const items = screensFor(role)
  const selected = (item: NavItem) => item.path === '/' ? location.pathname === '/' : pathSelected(location.pathname, item.path)
  const renderItem = (item: NavItem) => <Link key={item.path} to={item.path} title={item.label} aria-label={item.label} aria-current={selected(item) ? 'page' : undefined} className={`shared-nav-button ${selected(item) ? 'selected' : ''}`}><Icon>{item.icon}</Icon><span className="shared-sidebar-text">{item.label}</span></Link>
  return <aside className={`shared-sidebar ${collapsed ? 'shared-sidebar-collapsed' : ''}`} aria-label="Main navigation">
    <div className="shared-sidebar-main">
      <Link to="/" className="shared-brand"><span><Icon>solar_power</Icon></span><b className="shared-sidebar-text">SunPower<small>SOLUTIONS ERP</small></b></Link>
      <nav className="shared-nav">
        {(['WORKSPACES', 'MY WORK', 'OPERATIONS'] as const).map(group => {
          const rows = items.filter(item => item.group === group)
          return rows.length ? <div key={group}><span className="shared-section shared-sidebar-text">{group}</span>{rows.map(item => <div key={item.path}>{renderItem(item)}{childScreens[item.path] && <details className="shared-sidebar-text"><summary>More {item.label} screens</summary>{childScreens[item.path].map(([path, label]) => <Link className="shared-nav-button" key={path} to={path}>{label}</Link>)}</details>}</div>)}</div> : null
        })}
      </nav>
    </div>
    <div className="shared-sidebar-bottom">{!role ? <button title="Sign in" aria-label="Sign in" onClick={() => navigate('/login')}>Sign in<Icon>login</Icon></button> : <button title="Sign out"  aria-label="Sign out" disabled={signOut.isPending} onClick={() => signOut.mutate()}><span className="shared-sidebar-text">Sign out</span><Icon>logout</Icon></button>}{role && signOut.isError && <p role="alert">{signOut.error.message}</p>}<span className="shared-sidebar-text">v4.2</span><button title={collapsed ? 'Expand menu' : 'Collapse menu'} aria-label={collapsed ? 'Expand navigation menu' : 'Collapse navigation menu'} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}><span className="shared-sidebar-text">{collapsed ? 'Expand Menu' : 'Collapse Menu'}</span><Icon>{collapsed ? 'keyboard_double_arrow_right' : 'keyboard_double_arrow_left'}</Icon></button></div>
  </aside>
}
