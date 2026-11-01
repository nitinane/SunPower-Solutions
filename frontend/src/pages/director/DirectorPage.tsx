import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link } from 'react-router-dom'
import { getDashboardSummary } from '../../api/reports'
import { ApiError } from '../../api/client'
import { ChartContainer } from '../../components/dashboard/ChartContainer'
import { KpiCard } from '../../components/dashboard/KpiCard'
import { formatMoney } from '../../components/dashboard/format'

const PAGE_SIZE = 10

export function DirectorPage() {
  const report = useQuery({ queryKey: ['dashboard-summary'], queryFn: getDashboardSummary })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [profitFilter, setProfitFilter] = useState<'all' | 'profit' | 'loss'>('all')
  const jobs = useMemo(() => Object.entries(report.data?.profit_per_job ?? {}).map(([id, amount]) => ({ id, amount })), [report.data])
  const filtered = jobs.filter(job => (profitFilter === 'all' || (profitFilter === 'profit' ? Number(job.amount) >= 0 : Number(job.amount) < 0)) && job.id.toLowerCase().includes(search.trim().toLowerCase()))
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const rows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const chartData = [...jobs].sort((a, b) => Number(b.amount) - Number(a.amount)).slice(0, 8).map(job => ({ job: `#${job.id}`, profit: Number(job.amount) }))

  return <div className="ops-content director-content">
    <header className="ops-page-header director-header"><div><span>DIRECTOR WORKSPACE</span><h1>Business overview</h1><p>All-time operating and financial totals from PostgreSQL.</p></div><span className="ops-live"><i /> Live database</span></header>
    {report.isPending ? <section className="ops-state" aria-live="polite"><span className="ops-spinner"/><p>Loading business totals…</p></section> : report.isError ? <section className="ops-state"><h2>{report.error instanceof ApiError && report.error.status === 401 ? 'Sign in required' : 'Dashboard data unavailable'}</h2><p>{report.error.message}</p><button className="ops-secondary" onClick={() => void report.refetch()}>Try again</button></section> : <>
      <div className="director-section-label"><div><h2>Financial and operations snapshot</h2><p>Amounts reflect the backend report definitions.</p></div><span>All time</span></div>
      <section className="dash-kpi-grid" aria-label="Business totals">
        <KpiCard label="Customers" value={report.data.customer_count.toLocaleString('en-IN')} />
        <KpiCard label="Orders" value={report.data.order_count.toLocaleString('en-IN')} />
        <KpiCard label="Collected payments" value={formatMoney(report.data.total_revenue)} detail="Completed payments, net of refunds" tone="success" />
        <KpiCard label="Outstanding payments" value={formatMoney(report.data.outstanding_payments)} detail="Open order and service invoices" tone="warning" />
        <KpiCard label="Installation jobs" value={report.data.installation_count.toLocaleString('en-IN')} />
        <KpiCard label="Completed jobs" value={report.data.completed_jobs.toLocaleString('en-IN')} tone="success" />
        <KpiCard label="Unfinished jobs" value={report.data.unfinished_jobs.toLocaleString('en-IN')} tone="warning" />
        <KpiCard label="Open support tickets" value={report.data.open_support_tickets.toLocaleString('en-IN')} tone={report.data.open_support_tickets ? 'danger' : 'success'} />
      </section>

      <section className="director-visuals">
        <ChartContainer title="Job profitability" description="Top 8 jobs by backend-calculated profit contribution.">
          {chartData.length ? <div className="director-chart"><ResponsiveContainer width="100%" height={280}><BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 22, left: 8, bottom: 4 }}><CartesianGrid stroke="#eef0f2" horizontal={false}/><XAxis type="number" tickFormatter={value => `₹${new Intl.NumberFormat('en-IN', { notation: 'compact' }).format(value)}`} axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 11 }}/><YAxis type="category" dataKey="job" axisLine={false} tickLine={false} tick={{ fill: '#4b5563', fontSize: 11 }}/><Tooltip formatter={(value) => [formatMoney(value as number), 'Profit contribution']} cursor={{ fill: '#f8f5f7' }}/><Bar dataKey="profit" radius={[0, 4, 4, 0]}>{chartData.map((entry, index) => <Cell key={`${entry.job}-${index}`} fill={entry.profit < 0 ? '#e46e78' : '#21b799'}/>)}</Bar></BarChart></ResponsiveContainer></div> : <p className="dash-empty">No installation profit records are available yet.</p>}
        </ChartContainer>
        <section className="dash-panel director-note"><h2>What this report includes</h2><p>Collected payments are completed payment transactions, with refunds subtracted. Outstanding combines unpaid balances on non-cancelled orders and non-draft service invoices.</p><p>Job profit contribution uses order line margin (selling price less unit cost) minus assigned technician labour. The current API does not return monthly trends, job customer details, material/labour breakdowns or date-filtered aggregates.</p><Link to="/reports">Open reports <span aria-hidden="true">→</span></Link></section>
      </section>

      <ChartContainer title="Profit contribution by installation" description="Search and filter the live per-job results.">
        <div className="director-table-toolbar"><label className="director-search"><span className="material-symbols-outlined">search</span><input aria-label="Search jobs" placeholder="Search job reference" value={search} onChange={event => { setSearch(event.target.value); setPage(0) }}/></label><select aria-label="Filter by profitability" value={profitFilter} onChange={event => { setProfitFilter(event.target.value as typeof profitFilter); setPage(0) }}><option value="all">All results</option><option value="profit">Profitable</option><option value="loss">Loss-making</option></select><button className="ops-clear" onClick={() => { setSearch(''); setProfitFilter('all'); setPage(0) }}>Clear filters</button></div>
        <div className="ops-table-wrap director-table-wrap"><table className="ops-table director-table"><thead><tr><th>Job reference</th><th>Profit contribution</th><th>Result</th><th>Records</th></tr></thead><tbody>{rows.map(job => <tr key={job.id}><td><strong>Job #{job.id}</strong></td><td className={Number(job.amount) < 0 ? 'money-loss' : 'money-profit'}>{formatMoney(job.amount)}</td><td><span className={`profit-pill ${Number(job.amount) < 0 ? 'loss' : 'profit'}`}>{Number(job.amount) < 0 ? 'Loss' : 'Profit'}</span></td><td><Link to="/installations">View installations</Link></td></tr>)}{!rows.length && <tr><td colSpan={4} className="dash-empty-cell">No jobs match these filters.</td></tr>}</tbody></table></div>
        <div className="director-pagination"><span>{filtered.length ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, filtered.length)} of ${filtered.length} jobs` : '0 jobs'}</span><div><button className="ops-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button><button className="ops-secondary" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</button></div></div>
      </ChartContainer>
    </>}
  </div>
}
