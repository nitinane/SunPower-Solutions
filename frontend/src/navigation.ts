// The shared route permission map. Admin may open every staff screen.
export const routeRoles: Record<string, string[]> = {
  '/': ['director'], '/technician': ['technician'], '/warehouse': ['warehouse'],
  '/office': ['director', 'office'], '/director': ['director'],
  '/support': ['director', 'office', 'support'], '/customers': ['director', 'office', 'support'],
  '/installations': ['director', 'manager', 'office'], '/inventory': ['director', 'office', 'warehouse'],
  '/reports': ['director'], '/settings': ['director', 'manager', 'office', 'support', 'warehouse', 'surveyor', 'technician'],
  '/warehouse/dispatches': ['warehouse', 'director'], '/warehouse/dispatches/:id': ['warehouse', 'director'], '/warehouse/receiving': ['warehouse', 'director'],
  '/technician/today': ['technician'], '/technician/surveys/:id': ['technician'],
  '/technician/jobs/:id': ['technician'], '/technician/tickets/:id': ['technician'],
  '/surveyor/surveys': ['surveyor'], '/surveyor/surveys/:id': ['surveyor'],
  '/manager/schedule': ['manager'], '/support/tickets/:id': ['support', 'office', 'director'],
}
export function canOpen(role: string | undefined, path: string) {
  return !!role && (role === 'admin' || (routeRoles[path] ?? []).includes(role))
}
export type NavItem = { icon: string; label: string; path: string; permission?: string; group: 'WORKSPACES' | 'MY WORK' | 'OPERATIONS' }
export const navigation: NavItem[] = [
  { icon: 'dashboard', label: 'Owner Dashboard', path: '/', group: 'WORKSPACES' },
  { icon: 'engineering', label: 'Technician Demo', path: '/technician', group: 'WORKSPACES' },
  { icon: 'inventory_2', label: 'Warehouse Demo', path: '/warehouse', group: 'WORKSPACES' },
  { icon: 'query_stats', label: 'Director', path: '/director/overview', permission: '/director', group: 'MY WORK' },
  { icon: 'support_agent', label: 'Office Sales', path: '/office/enquiries', permission: '/office', group: 'MY WORK' },
  { icon: 'today', label: 'My Day', path: '/technician/today', group: 'MY WORK' },
  { icon: 'move_to_inbox', label: 'Receiving', path: '/warehouse/receiving', group: 'MY WORK' },
  { icon: 'local_shipping', label: 'Dispatches', path: '/warehouse/dispatches', group: 'MY WORK' },
  { icon: 'calendar_month', label: 'Crew Schedule', path: '/manager/schedule', group: 'MY WORK' },
  { icon: 'assignment', label: 'My Surveys', path: '/surveyor/surveys', group: 'MY WORK' },
  { icon: 'support', label: 'Support', path: '/support', group: 'MY WORK' },
  ...[['groups', 'Customers', '/customers'], ['wb_sunny', 'Installations', '/installations'], ['warehouse', 'Inventory', '/inventory'], ['monitoring', 'Reports', '/reports'], ['settings', 'Settings', '/settings']].map(([icon, label, path]) => ({ icon, label, path, group: 'OPERATIONS' as const })),
]
export function screensFor(role?: string) {
  return navigation.filter(item => canOpen(role, item.permission ?? item.path) && !(role === 'technician' && item.group === 'WORKSPACES'))
}

export const childScreens: Record<string, [string, string][]> = {
  '/office/enquiries': [['/office/surveys', 'Survey booking'], ['/office/quotes', 'Quotes & print'], ['/office/orders', 'Orders & payments'], ['/office/invoices', 'Invoices & print'], ['/office/repairs', 'Repair intake'], ['/office/subsidies', 'Subsidies']],
  '/director/overview': [['/director/surveys', 'Survey Review'], ['/director/pay', 'Technician pay runs'], ['/director/sharing', 'Shared links']],
}
