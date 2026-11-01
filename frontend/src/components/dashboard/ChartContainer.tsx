import type { ReactNode } from 'react'

export function ChartContainer({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return <section className="dash-panel"><header className="dash-panel-heading"><div><h2>{title}</h2>{description && <p>{description}</p>}</div></header>{children}</section>
}
