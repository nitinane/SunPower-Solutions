import type { ReactNode } from 'react'

export function KpiCard({ label, value, detail, tone = 'primary' }: { label: string; value: ReactNode; detail?: string; tone?: 'primary' | 'success' | 'warning' | 'danger' }) {
  return <article className={`dash-kpi dash-kpi-${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>
}
