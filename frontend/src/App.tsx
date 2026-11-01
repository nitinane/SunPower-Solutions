import { useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { SharedSidebar } from './components/SharedSidebar'
import { TopActions } from './components/TopActions'
import { getCurrentUser } from './api/auth'
import { ApiError, apiFetch } from './api/client'
import { getDashboardSummary, getDashboardTrend, getDirectorSurveys, type DashboardTrendPoint } from './api/director'
import { getOrders } from './api/sales'
import type { Page } from './api/enquiries'
import type { StockRow, DispatchSummary } from './api/inventory'
import type { MyToday, ScheduleRow } from './pages/field/contracts'
import { canOpen } from './navigation'
import { formatMoney, formatIst } from './utils/format'

type Workspace = 'owner' | 'tech' | 'warehouse'
const workspaceMeta = {
  owner: { title: 'Owner Workspace', subtitle: 'Sales, payments and operational approvals', role: 'director', path: '/', icon: 'shield_person' },
  tech: { title: 'Technician Field Workspace', subtitle: 'Your assigned surveys, installations and repair visits', role: 'technician', path: '/technician', icon: 'engineering' },
  warehouse: { title: 'Warehouse Workspace', subtitle: 'Stock levels and field dispatches', role: 'warehouse', path: '/warehouse', icon: 'inventory_2' },
}
function Icon({ children }: { children: string }) { return <span className="material-symbols-outlined" aria-hidden="true">{children}</span> }
const humanize = (value: string) => value.replaceAll('_', ' ')
function KpiCard({ id, label, value, icon, tone = 'primary', detail = '' }: { id: string; label: string; value: string; icon: string; tone?: string; detail?: string }) {
  return <article className="kpi-card" data-testid={id}><div className="kpi-top"><span>{label}</span><div className={`kpi-icon ${tone}`}><Icon>{icon}</Icon></div></div><div className="kpi-value-row"><strong>{value}</strong></div>{detail && <div className="kpi-footer"><span>{detail}</span></div>}</article>
}
function DataState({ queries, children }: { queries: { isPending: boolean; isError: boolean; error: Error | null; refetch: () => unknown }[]; children: ReactNode }) {
  const error = queries.find(query => query.isError)?.error
  if (error) return <section className="panel workspace-state" role="alert"><h2>Could not load live data</h2><p>{error.message}</p><button className="action-button" onClick={() => queries.forEach(query => void query.refetch())}>Try again</button></section>
  if (queries.some(query => query.isPending)) return <section className="panel workspace-state" role="status"><span className="spinner" />Loading live data…</section>
  return children
}

// Stock and dispatch totals cover every page, including catalogs larger than 100 items.
async function allPages<T>(path: string): Promise<T[]> {
  const first = await apiFetch<Page<T>>(`${path}?page=1&page_size=100`)
  const rest = await Promise.all(Array.from({ length: Math.max(0, Math.ceil(first.total / 100) - 1) }, (_, i) => apiFetch<Page<T>>(`${path}?page=${i + 2}&page_size=100`)))
  return [first, ...rest].flatMap(page => page.items)
}

function RevenueChart({ rows }: { rows: DashboardTrendPoint[] }) {
  // Numeric conversions are only for SVG coordinates; labels retain exact Decimal strings.
  const maximum = Math.max(1, ...rows.flatMap(row => [Number(row.booked_order_value), Number(row.payments_received)]))
  const x = (index: number) => 60 + index * 880 / Math.max(1, rows.length - 1)
  const y = (value: string) => 200 - Number(value) / maximum * 165
  const points = (key: 'booked_order_value' | 'payments_received') => rows.map((row, i) => `${x(i)},${y(row[key])}`).join(' ')
  return <section className="panel trend-panel"><div className="panel-heading"><div><div className="heading-row"><Icon>monitoring</Icon><h2>12-Month Sales & Payment Trend</h2><span className="tag cyan">{rows[0]?.month} – {rows.at(-1)?.month}</span></div><p>Confirmed order value and completed payments by IST month, through today</p></div><div className="heading-actions"><span className="legend"><i className="dot purple"/>Booked orders (including GST)</span><span className="legend"><i className="dot teal"/>Payments received</span><Link className="action-button" to="/reports">View reports</Link></div></div>
    <div className="chart-wrap"><svg viewBox="0 0 1000 240" role="img" aria-label="Revenue trend chart"><title>Monthly booked orders and payments received</title>{[35, 90, 145, 200].map(y => <line key={y} x1="45" x2="955" y1={y} y2={y} className="grid-line"/>)}<polyline className="line purple-line" points={points('booked_order_value')}/><polyline className="line teal-line" points={points('payments_received')}/>{rows.map((row, i) => <g key={row.month} className="chart-point"><circle cx={x(i)} cy={y(row.booked_order_value)} r="4"><title>{row.month}: booked {formatMoney(row.booked_order_value)}, received {formatMoney(row.payments_received)}</title></circle><text x={x(i)} y="225">{row.month.slice(2)}</text></g>)}</svg></div>
    <details className="live-trend-values"><summary>View monthly values</summary><div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Month (IST)</th><th>Booked order value</th><th>Payments received</th></tr></thead><tbody>{rows.map(row => <tr key={row.month}><td>{row.month}</td><td>{formatMoney(row.booked_order_value)}</td><td>{formatMoney(row.payments_received)}</td></tr>)}</tbody></table></div></details>
  </section>
}

function OwnerDashboard() {
  const summary = useQuery({ queryKey: ['workspace', 'summary'], queryFn: () => getDashboardSummary('month'), refetchInterval: 30000 })
  const trend = useQuery({ queryKey: ['workspace', 'trend'], queryFn: () => getDashboardTrend(12), refetchInterval: 30000 })
  const orders = useQuery({ queryKey: ['workspace', 'orders'], queryFn: () => getOrders({ page_size: 20 }), refetchInterval: 30000 })
  const surveys = useQuery({ queryKey: ['workspace', 'approval-surveys'], queryFn: () => getDirectorSurveys('submitted', 1, 1), refetchInterval: 30000 })
  const jobs = useQuery({ queryKey: ['workspace', 'unscheduled'], queryFn: () => apiFetch<Page<ScheduleRow>>('/installation-jobs?status=planned&page_size=1'), refetchInterval: 30000 })
  const cards = summary.data?.cards
  const active = orders.data?.items.filter(order => !['installed', 'completed', 'cancelled'].includes(order.status)).slice(0, 6) ?? []
  return <div className="workspace-content"><DataState queries={[summary, trend, orders, surveys, jobs]}>{cards && <>
    <section className="kpi-grid"><KpiCard id="owner-orders" label="Confirmed Orders (MTD)" value={String(cards.orders_confirmed)} icon="solar_power" tone="secondary" detail="This IST calendar month"/><KpiCard id="owner-payments" label="Payments Received (MTD)" value={formatMoney(cards.payments_received)} icon="payments" detail="Completed payments this month"/><KpiCard id="owner-unfinished" label="Unfinished Projects" value={String(cards.unfinished_jobs)} icon="construction" tone="tertiary" detail="All confirmed unfinished orders"/><KpiCard id="owner-repairs" label="Open Repairs" value={String(cards.open_repairs)} icon="build_circle" tone="error" detail="Excludes closed and cancelled tickets"/></section>
    <RevenueChart rows={trend.data ?? []}/>
    <section className="project-grid"><div className="panel projects-panel"><div className="panel-toolbar"><div><h2>Recent Active Projects</h2><p>Active projects among the 20 most recent orders; stage is the current order status</p></div><Link className="action-button primary" to="/office/enquiries"><Icon>add</Icon>New enquiry</Link></div><div className="project-list" data-testid="owner-projects">{!active.length && <p className="workspace-empty">No active projects among recent orders.</p>}{active.map(order => <div className="project-row" key={order.id}><div className="project-title"><strong>{order.order_number}</strong><span>{order.customer_name}</span><span className="status secondary">{humanize(order.status)}</span></div><div className="project-meta"><span>Order value {formatMoney(order.total)}</span><span>Booked {formatIst(order.created_at)}</span></div></div>)}</div><Link className="view-all" to="/office/orders">View all orders <Icon>arrow_forward</Icon></Link></div>
    <div className="panel approvals-panel"><div className="panel-toolbar"><div><h2>Approval Queue</h2><p>Live operational queues</p></div></div>{[
      ['Surveys waiting for approval', surveys.data?.total ?? 0, '/director/surveys', 'Review'],
      ['Unscheduled jobs', jobs.data?.total ?? 0, '/installations', 'Schedule'],
      ['Open repairs', cards.open_repairs, '/support', 'Open'],
    ].map(([label, count, path, action]) => <div className="approval-card" key={label}><div className="approval-icon"><Icon>assignment</Icon></div><div><strong>{label}</strong><p>{count} waiting</p></div><Link className="action-button" to={String(path)}>{action}</Link></div>)}</div></section>
  </>}</DataState></div>
}

function TechnicianWorkspace() {
  const today = useQuery({ queryKey: ['workspace', 'my-today'], queryFn: () => apiFetch<MyToday>('/me/today'), refetchInterval: 30000 })
  const data = today.data
  const work = data ? [
    ...data.surveys.map(row => ({ id: `survey-${row.id}`, name: row.customer_name, status: row.status, address: row.site.address_line1, label: 'Survey', path: `/technician/surveys/${row.id}` })),
    ...data.installation_jobs.map(row => ({ id: `job-${row.job_id}`, name: row.customer_name, status: row.status, address: row.site.address_line1, label: 'Installation', path: `/technician/jobs/${row.job_id}` })),
    ...data.ticket_visits.map(row => ({ id: `ticket-${row.id}`, name: row.customer_name, status: row.status, address: row.site.address_line1, label: row.ticket_number, path: `/technician/tickets/${row.id}` })),
  ] : []
  return <div className="workspace-content secondary-workspace technician-view"><DataState queries={[today]}>{data && <>
    <section className="kpi-grid"><KpiCard id="tech-jobs" label="Today's Installations" value={String(data.installation_jobs.length)} icon="solar_power" tone="secondary" detail={data.date}/><KpiCard id="tech-surveys" label="Today's Surveys" value={String(data.surveys.length)} icon="assignment" detail={data.date}/><KpiCard id="tech-repairs" label="Today's Repair Visits" value={String(data.ticket_visits.length)} icon="build_circle" tone="error" detail={data.date}/><KpiCard id="tech-total" label="Total Assigned Today" value={String(work.length)} icon="today" tone="tertiary" detail="Your assignments only"/></section>
    <section className="panel queue-panel"><div className="panel-toolbar"><div><h2>Today's Job Queue</h2><p>{data.date} · Your live assigned work</p></div><div className="toolbar-actions"><button className="action-button" onClick={() => void today.refetch()}><Icon>refresh</Icon>Refresh</button><Link className="action-button primary" to="/technician/today">Open My Day</Link></div></div><div data-testid="tech-queue">{!work.length && <p className="workspace-empty">No work assigned for today.</p>}{work.map((row, index) => <div className="queue-row enhanced-queue-row" key={row.id}><span className="queue-number">{index + 1}</span><div className="queue-main"><strong>{row.name}</strong><p>{row.label} · {row.address}</p></div><span className="queue-detail">{humanize(row.status)}</span><Link className="queue-action" to={row.path}>Open <Icon>arrow_forward</Icon></Link></div>)}</div></section>
  </>}</DataState></div>
}

function WarehouseWorkspace() {
  const [showLowOnly, setShowLowOnly] = useState(true)
  const stock = useQuery({ queryKey: ['workspace', 'stock'], queryFn: () => allPages<StockRow>('/stock'), refetchInterval: 30000 })
  const dispatches = useQuery({ queryKey: ['workspace', 'dispatches'], queryFn: () => allPages<DispatchSummary>('/dispatches'), refetchInterval: 30000 })
  const low = stock.data?.filter(row => row.low_stock) ?? []
  const waiting = dispatches.data?.filter(row => ['draft', 'packed'].includes(row.status)) ?? []
  const inTransit = dispatches.data?.filter(row => row.status === 'dispatched') ?? []
  const refresh = () => { void stock.refetch(); void dispatches.refetch() }
  return <div className="workspace-content secondary-workspace warehouse-view"><DataState queries={[stock, dispatches]}>
    <section className="kpi-grid"><KpiCard id="warehouse-products" label="Stock Products" value={String(stock.data?.length ?? 0)} icon="inventory_2" detail="Across all catalog pages"/><KpiCard id="warehouse-low" label="Low Stock Products" value={String(low.length)} icon="warning" tone="error" detail="Backend stock thresholds"/><KpiCard id="warehouse-waiting" label="Pick Lists Waiting" value={String(waiting.length)} icon="local_shipping" tone="tertiary" detail="Draft and packed dispatches"/><KpiCard id="warehouse-transit" label="In Transit" value={String(inTransit.length)} icon="directions_car" tone="secondary" detail="Dispatched, awaiting delivery"/></section>
    <section className="panel queue-panel"><div className="panel-toolbar"><div><h2>{showLowOnly ? 'Low Stock' : 'Stock Overview'}</h2><p>On-hand quantities from stock receipts and movements</p></div><div className="toolbar-actions"><button className="action-button" onClick={() => setShowLowOnly(!showLowOnly)}>{showLowOnly ? 'Show all stock' : 'Show low stock'}</button><Link className="action-button primary" to="/warehouse/receiving">Receive stock</Link></div></div><div data-testid="warehouse-stock">{showLowOnly && !low.length && <p className="workspace-empty">No products below the stock threshold.</p>}{(showLowOnly ? low : stock.data ?? []).map(row => <div className="queue-row enhanced-queue-row" key={row.product_id}><Icon>inventory_2</Icon><div className="queue-main"><strong>{row.name}</strong><p>{row.sku}</p></div><span className="queue-detail">{row.on_hand} on hand</span><span className={`status ${row.low_stock ? 'warning' : 'secondary'}`}>{row.low_stock ? 'Low stock' : 'In stock'}</span></div>)}</div></section>
    <section className="panel queue-panel"><div className="panel-toolbar"><div><h2>Field Dispatch Manifest</h2><p>Recent dispatches and their current status</p></div><div className="toolbar-actions"><button className="action-button" onClick={refresh}><Icon>refresh</Icon>Refresh</button><Link className="action-button primary" to="/warehouse/dispatches">All dispatches</Link></div></div><div data-testid="warehouse-dispatches">{!dispatches.data?.length && <p className="workspace-empty">No dispatches yet. Confirm an order with its first payment.</p>}{[...(dispatches.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id).slice(0, 8).map((row, index) => <div className="queue-row enhanced-queue-row" key={row.id}><span className="queue-number">{index + 1}</span><div className="queue-main"><strong>{row.dispatch_number}</strong><p>{row.customer.name} · {row.order_number}</p></div><span className="queue-detail warehouse-detail">{humanize(row.status)}</span><Link className="queue-action" to={`/warehouse/dispatches/${row.id}`}>Open manifest</Link></div>)}</div></section>
  </DataState></div>
}

export function HomePage({ initialWorkspace = 'owner' }: { initialWorkspace?: Workspace }) {
  const { pathname } = useLocation()
  const workspace: Workspace = pathname === '/technician' ? 'tech' : pathname === '/warehouse' ? 'warehouse' : initialWorkspace
  const meta = workspaceMeta[workspace]
  const session = useQuery({ queryKey: ['auth-me'], queryFn: getCurrentUser, retry: false })
  const allowed = !session.isError && canOpen(session.data?.role, meta.path)
  const unavailable = session.isError && !(session.error instanceof ApiError && session.error.status === 401)
  return <div className="app-shell"><SharedSidebar/><div className="main-area"><header className="topbar"><div className="breadcrumb"><span>SunPower OS</span><Icon>chevron_right</Icon><span className="active-workspace">Active Workspace: {workspace === 'owner' ? 'Owner' : workspace === 'tech' ? 'Technician' : 'Warehouse'}</span></div><TopActions/></header><main><section className="workspace-banner"><div className="banner-title"><div className={`banner-icon ${workspace}`}><Icon>{meta.icon}</Icon></div><div><div className="heading-row"><h1>{meta.title}</h1></div><p>{meta.subtitle}</p></div></div></section>
    {session.isPending ? <section className="panel workspace-state" role="status">Checking staff session…</section> : unavailable ? <section className="panel workspace-state" role="alert"><h2>Could not verify your session</h2><p>{session.error.message}</p><button className="action-button" onClick={() => void session.refetch()}>Try again</button></section> : !allowed ? <section className="panel workspace-state"><h2>Sign in as {meta.role} to see live data</h2><Link className="action-button primary" to="/login" state={{ from: pathname }}>Sign in</Link></section> : workspace === 'owner' ? <OwnerDashboard/> : workspace === 'tech' ? <TechnicianWorkspace/> : <WarehouseWorkspace/>}
  </main></div></div>
}
