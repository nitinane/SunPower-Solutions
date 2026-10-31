import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { getSharedDashboard } from '../../api/public'
import { formatIst, formatMoney } from '../../utils/format'

export function SharedDashboardPage() {
  const { token = '' } = useParams()
  const report = useQuery({ queryKey: ['public-dashboard', token], queryFn: () => getSharedDashboard(token), enabled: token.length > 0, retry: false })
  if (report.isPending) return <main className="public-report-page"><div className="screen-state"><span className="spinner" /><p>Loading shared report…</p></div></main>
  if (report.isError) return <main className="public-report-page"><div className="screen-state"><span className="state-icon">↗</span><h1>Report unavailable</h1><p>This link may have expired or been revoked. Ask the report owner for a current link.</p></div></main>
  const data = report.data
  const cards = [['Payments received', formatMoney(data.cards.payments_received)], ['Profit', formatMoney(data.cards.profit)], ['Confirmed orders', data.cards.orders_confirmed], ['New enquiries', data.cards.new_enquiries], ['Unfinished jobs', data.cards.unfinished_jobs], ['Open repairs', data.cards.open_repairs]] as const
  return <main className="public-report-page"><header><span className="eyebrow">SUNPOWER SOLUTIONS · SHARED REPORT</span><h1>Operations overview</h1><p>{data.period[0].toUpperCase() + data.period.slice(1)} · {formatIst(data.from_at)} – {formatIst(data.to_at)}</p></header><section className="report-grid">{cards.map(([label, value]) => <article className="report-card" key={label}><span>{label}</span><strong>{value}</strong><small>Read-only summary</small></article>)}</section><section className="public-report-list"><h2>Profit by job</h2>{data.profit_per_job.length ? data.profit_per_job.map(job => <article key={job.order_number}><div><strong>{job.order_number}</strong><span>{job.customer} · {job.system_kw} kW</span></div><b>{formatMoney(job.profit)}</b></article>) : <p>No job profit data for this period.</p>}</section><p className="form-footnote">This page is read-only and available to anyone with this share link.</p></main>
}
