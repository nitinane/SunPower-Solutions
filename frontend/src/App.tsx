import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SharedSidebar } from './components/SharedSidebar'

type Workspace = 'owner' | 'tech' | 'warehouse'

const workspaceMeta: Record<Workspace, { title: string; subtitle: string; icon: string; user: string; role: string }> = {
  owner: { title: 'Owner Workspace', subtitle: 'Executive Strategy, Cross-Operational Profitability & Resource Clearance', icon: 'shield_person', user: 'Marcus Vance', role: 'Managing Director' },
  tech: { title: 'Technician Field Workspace', subtitle: 'Live Job Queue, Safety Compliance & Installation Sign-Offs', icon: 'engineering', user: 'Chris Adams', role: 'Senior Field Technician' },
  warehouse: { title: 'Warehouse Workspace', subtitle: 'Hardware Serialization Gate, Stock Allocation & Morning Dispatch Staging', icon: 'inventory_2', user: 'Dave Kendrick', role: 'Depot Logistics Lead' },
}

function Icon({ children }: { children: string }) {
  return <span className="material-symbols-outlined" aria-hidden="true">{children}</span>
}

function ActionButton({ children, onClick, primary = false }: { children: React.ReactNode; onClick: () => void; primary?: boolean }) {
  return <button className={`action-button ${primary ? 'primary' : ''}`} onClick={onClick}>{children}</button>
}

function OwnerDashboard({ notify }: { notify: (message: string) => void }) {
  const projects = [
    ['SPS-2026-0891', 'Bramhall Estates, Pune', 'Roof Mount • 42.6 kWp', 'Installation', 78, 'secondary'],
    ['SPS-2026-0899', 'Suryodaya Logistics Hub, Mumbai', 'Commercial • 128.4 kWp', 'DISCOM Clearance', 52, 'warning'],
    ['SPS-2026-0904', 'Greenview Residence, Bengaluru', 'Battery Hybrid • 9.5 kWp', 'Survey Complete', 34, 'primary'],
    ['SPS-2026-0908', 'Noida Business Park, Uttar Pradesh', 'Commercial • 86.2 kWp', 'Materials Staged', 18, 'tertiary'],
  ] as const

  return <div className="workspace-content">
    <section className="kpi-grid">
      <KpiCard label="Completed Installs (MTD)" value="42" detail="↑ 12.4% vs last month" icon="solar_power" tone="secondary" footLeft="Target: 48 installs" footRight="87.5% achieved" />
      <KpiCard label="Gross Booked Revenue" value="₹38.45 Lakh" detail="↑ ₹5.2 Lakh margin" icon="payments" tone="primary" footLeft="Average System: ₹9,155" footRight="32.4% Net Margin" />
      <KpiCard label="Fleet Dispatch Rate" value="94.2%" detail="✓ 8/8 Vans Active" icon="local_shipping" tone="tertiary" footLeft="Crew Lead: C. Adams" footRight="0 Breakdowns" />
      <KpiCard label="Pending Milestone Invoices" value="₹6.48 Lakh" detail="◷ 6 Awaiting MNRE" icon="receipt_long" tone="error" footLeft="UPI / Bank Transfer" footRight="Avg 4.1 days lag" />
    </section>

    <section className="panel trend-panel">
      <div className="panel-heading">
        <div><div className="heading-row"><Icon>monitoring</Icon><h2>12-Month Sales & Installation Revenue Trend</h2><span className="tag cyan">Apr 2025 – Mar 2026</span></div><p>Gross closed contracts vs billed milestone disbursements (₹3.84 Cr TTM cumulative across residential & commercial runs)</p></div>
        <div className="heading-actions"><span className="legend"><i className="dot purple" />Booked Contracts (₹)</span><span className="legend"><i className="dot teal" />Milestone Cash Received</span><ActionButton onClick={() => notify('Exporting Revenue Financial Audit (FY25-26)')}><Icon>download</Icon> Export P&amp;L</ActionButton></div>
      </div>
      <div className="chart-wrap">
        <svg viewBox="0 0 1000 240" role="img" aria-label="Revenue trend chart">
          <defs><linearGradient id="areaPurple" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#57344f" stopOpacity=".24" /><stop offset="1" stopColor="#57344f" stopOpacity="0" /></linearGradient><linearGradient id="areaTeal" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#00696e" stopOpacity=".18" /><stop offset="1" stopColor="#00696e" stopOpacity="0" /></linearGradient></defs>
          {[30, 80, 130, 180].map(y => <line key={y} x1="40" x2="960" y1={y} y2={y} className="grid-line" />)}
          <text x="8" y="34">₹40L</text><text x="8" y="84">₹30L</text><text x="8" y="134">₹20L</text><text x="8" y="184">₹10L</text>
          <polygon fill="url(#areaPurple)" points="60,165 140,150 220,135 300,105 380,80 460,70 540,85 620,95 700,75 780,60 860,45 940,38 940,210 60,210" />
          <polyline className="line purple-line" points="60,165 140,150 220,135 300,105 380,80 460,70 540,85 620,95 700,75 780,60 860,45 940,38" />
          <polygon fill="url(#areaTeal)" points="60,180 140,170 220,152 300,128 380,102 460,94 540,108 620,118 700,98 780,82 860,68 940,55 940,210 60,210" />
          <polyline className="line teal-line" points="60,180 140,170 220,152 300,128 380,102 460,94 540,108 620,118 700,98 780,82 860,68 940,55" />
          {['Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar'].map((month, i) => <g key={month} className="chart-point" onClick={() => notify(`${month} 2025: Revenue details opened`)}><circle cx={60 + i * 80} cy={165 - [0,15,30,60,85,95,80,70,90,105,120,127][i]} r={i === 11 ? 6 : 5} /><text x={60 + i * 80} y="226">{month}</text></g>)}
        </svg>
      </div>
      <div className="trend-stats"><Stat label="TTM Closed Revenue" value="₹3.84 Cr" /><Stat label="Avg Monthly Growth" value="+6.8% MoM" tone="teal" /><Stat label="UPI / Bank Realization Rate" value="96.4% on Schedule" tone="green" /></div>
    </section>

    <section className="project-grid">
      <div className="panel projects-panel">
        <div className="panel-toolbar"><div><h2>Active Commercial & Residential Projects</h2><p>Live installation tracker showing current stage completion across regional clusters</p></div><div className="toolbar-actions"><ActionButton onClick={() => notify('Filtered: All Regional Hubs Active')}><Icon>filter_list</Icon> All Hubs</ActionButton><ActionButton primary onClick={() => notify('New Solar Project Creation Modal Opened')}><Icon>add</Icon> New Project</ActionButton></div></div>
        <div className="project-list">{projects.map(([id, location, type, status, progress, tone]) => <div className="project-row" key={id}><div className="project-title"><strong>{id}</strong><span>{location}</span><span className={`status ${tone}`}>{status}</span></div><div className="project-meta"><span>{type}</span><strong>{progress}%</strong></div><div className="progress-track"><span className={tone} style={{ width: `${progress}%` }} /></div></div>)}</div>
        <button className="view-all" onClick={() => notify('Opening full project register')}>View all 24 active projects <Icon>arrow_forward</Icon></button>
      </div>
      <div className="panel approvals-panel"><div className="panel-toolbar"><div><h2>Approval Queue</h2><p>Items requiring executive action</p></div><span className="tag red">3 Requires Action</span></div>{[['DISCOM clearance', 'SPS-2026-0899 needs grid approval', 'Approve'], ['Purchase order', 'Battery buffer replenishment • ₹18,420', 'Review'], ['Milestone invoice', 'SPS-2026-0872 • ₹12,800', 'Review']].map(([title, detail, action]) => <div className="approval-card" key={title}><div className="approval-icon"><Icon>{action === 'Approve' ? 'verified' : 'receipt_long'}</Icon></div><div><strong>{title}</strong><p>{detail}</p></div><button onClick={() => notify(`${title} ${action.toLowerCase()}d`)}>{action}</button></div>)}</div>
    </section>
  </div>
}

function KpiCard({ label, value, detail, icon, tone, footLeft, footRight }: { label: string; value: string; detail: string; icon: string; tone: string; footLeft: string; footRight: string }) {
  return <article className="kpi-card"><div className="kpi-top"><span>{label}</span><div className={`kpi-icon ${tone}`}><Icon>{icon}</Icon></div></div><div className="kpi-value-row"><strong>{value}</strong><span className={`kpi-detail ${tone}`}>{detail}</span></div><div className="kpi-footer"><span>{footLeft}</span><b>{footRight}</b></div></article>
}

function Stat({ label, value, tone = 'purple' }: { label: string; value: string; tone?: string }) {
  return <div className="trend-stat"><span>{label}</span><strong className={tone}>{value}</strong></div>
}

function SecondaryWorkspace({ workspace, notify }: { workspace: Workspace; notify: (message: string) => void }) {
  const tech = workspace === 'tech'
  const cards = tech
    ? [['Today’s Assigned Jobs', '4', 'Rooftop sites', 'solar_power'], ['Priority Target', 'Suryodaya Logistics Hub', '28.8 kWp Commercial', 'flag'], ['Survey Sign-Offs', '2', 'Pending upload', 'assignment_late'], ['Service & Warranty', '3', 'Tickets in queue', 'build_circle']]
    : [['Total Valuation', '₹24.14 Lakh', 'Asset turnover · 18.4 days avg', 'payments'], ['Solar PV Panels', '184', 'Waaree 540W / Adani · 74% racked', 'solar_power'], ['Inverters in Racks', '28', 'Sungrow, Growatt · 19 allocated', 'electric_meter'], ['ESS Battery Packs', '42', 'Amaron & Exide · 84% HAZMAT', 'battery_charging_full'], ['Dispatch Slips', '6', '4 morning runs · 11 pending scans', 'local_shipping']]
  const jobs = tech
    ? [['Suryodaya Logistics Hub', 'Crew #04 · In Progress', '28.8 kWp', 'directions_car'], ['Greenview Residence', 'Crew #02 · Queued', '9.5 kWp', 'schedule'], ['Bramhall Estates', 'Crew #01 · Staged', '42.6 kWp', 'task_alt']]
    : [['DSP-2026-089', 'Pune Solar Farm Phase 2', '5/5 Verified · Ready to Pack', 'Seal Cargo'], ['DSP-2026-090', 'Bengaluru 8.4kW Hybrid', '6/8 Verified · Picking', 'Continue Pick'], ['DSP-2026-091', 'Noida Business Park', '0/12 Verified · Awaiting scan', 'Open Manifest']]
  return <div className={`workspace-content secondary-workspace ${tech ? 'technician-view' : 'warehouse-view'}`}>
    {tech ? <section className="alert-grid"><div className="safety-card"><div className="safety-icon"><Icon>health_and_safety</Icon></div><div><strong>Daily Safety & Risk Clearance: Certified <Icon>verified</Icon></strong><p>Wind speed below 20 km/h. Rooftop tie-off lines, Class-0 electrical PPE, and arc-flash kits inspected.</p></div><div className="secondary-actions"><ActionButton onClick={() => notify('Serial scanner opened')}><Icon>qr_code_scanner</Icon> Scan Serial</ActionButton><ActionButton primary onClick={() => notify('Safety Form JSA certified for Crew #04')}><Icon>checklist</Icon> Safety Form JSA</ActionButton></div></div><div className="weather-card"><span>SITE WEATHER WINDOW · IST</span><strong>32°C • Clear Solar Irradiance</strong><small>Peak Sun Window: 10:45 AM - 3:30 PM IST</small><Icon>wb_sunny</Icon></div></section> : <section className="reorder-banner"><div className="safety-icon"><Icon>notification_important</Icon></div><div><strong>Procurement Buffer Threshold Triggered <span className="critical-tag">CRITICAL · QTY: 2</span></strong><p><b>Growatt MIN 5000TL-XH 5kW Hybrid Inverter</b> is below its safety threshold. Four projects are pending allocation this week.</p></div><ActionButton onClick={() => notify('Auto-PO triggered for Growatt MIN 5000TL-XH')}>Trigger Auto-PO</ActionButton></section>}
    <section className={`secondary-cards ${tech ? '' : 'warehouse-cards'}`}>{cards.map(([label, value, detail, icon]) => <article className="secondary-card" key={label}><div><span>{label}</span><Icon>{icon}</Icon></div><strong>{value}</strong><small>{detail}</small><hr /><button onClick={() => notify(`${label} details opened`)}>View details <Icon>arrow_forward</Icon></button></article>)}</section>
    <section className="panel queue-panel"><div className="panel-toolbar"><div><h2>{tech ? 'Today’s Job Queue & Dispatch Checklist' : 'Picking Station & Field Dispatch Manifest'}</h2><p>{tech ? 'Real-time status updates sync directly to central ERP' : 'Live serial number reconciliation for crew vehicle morning loading'}</p></div><div className="toolbar-actions"><ActionButton onClick={() => notify('Manifest refreshed')}><Icon>refresh</Icon> Refresh</ActionButton><ActionButton primary onClick={() => notify(tech ? 'Job queue filter opened' : 'Dispatch manifest opened')}><Icon>filter_list</Icon> {tech ? 'Filter Queue' : 'Open Manifest'}</ActionButton></div></div>{jobs.map(([id, title, detail, action], index) => <div className="queue-row enhanced-queue-row" key={id}><span className={`queue-number ${index === 0 ? 'active' : ''}`}>{index + 1}</span><div className="queue-main"><strong>{tech ? title : id}</strong><p>{tech ? `${detail} · ${title}` : title}</p></div><span className={tech ? 'queue-detail' : 'queue-detail warehouse-detail'}>{tech ? detail : detail}</span><button className="queue-action" onClick={() => notify(`${action} opened`)}>{tech ? <Icon>{action}</Icon> : action}</button></div>)}</section>
    {tech && <section className="technician-footer"><div><Icon>verified</Icon><span><strong>Field compliance is current</strong><small>Safety forms, PPE checks and site evidence sync to the central ERP.</small></span></div><button onClick={() => notify('Document upload dialog opened')}>Upload site evidence <Icon>arrow_forward</Icon></button></section>}
  </div>
}

export function HomePage({ initialWorkspace = 'owner' }: { initialWorkspace?: Workspace }) {
  const { pathname } = useLocation()
  const workspace: Workspace = pathname === '/technician' ? 'tech' : pathname === '/warehouse' ? 'warehouse' : initialWorkspace
  const [toast, setToast] = useState('')
  const meta = workspaceMeta[workspace]
  const notify = (message: string) => { setToast(message); window.setTimeout(() => setToast(''), 2600) }
  return <div className="app-shell"><SharedSidebar /><div className="main-area"><header className="topbar"><div className="breadcrumb"><span>SunPower OS</span><Icon>chevron_right</Icon><span className="active-workspace"><i style={{ backgroundColor: workspace === 'owner' ? '#57344f' : workspace === 'tech' ? '#00696e' : '#34451e' }} />Active Workspace: {workspace === 'owner' ? 'Owner' : workspace === 'tech' ? 'Technician' : 'Warehouse'}</span></div><div className="top-actions"><button onClick={() => notify('Barcode scanner opened')}><Icon>qr_code_scanner</Icon><span>Quick Scan</span></button><div className="capacity"><span>GRID CAPACITY</span><b>2.4 MW Active</b><Icon>bolt</Icon></div><button onClick={() => notify('You have 2 operational alerts')}><Icon>notifications</Icon><em /></button><button onClick={() => notify('ERP Help Guide opened')}><Icon>help</Icon></button><div className="user"><div><strong>{meta.user}</strong><small>{meta.role}</small></div><div className={`avatar ${workspace}`}><Icon>person</Icon></div></div></div></header>
      <main><section className="workspace-banner"><div className="banner-title"><div className={`banner-icon ${workspace}`}><Icon>{meta.icon}</Icon></div><div><div className="heading-row"><h1>{meta.title}</h1><span className="tag purple">Active Scope</span></div><p>{meta.subtitle}</p></div></div></section>{workspace === 'owner' ? <OwnerDashboard notify={notify} /> : <SecondaryWorkspace workspace={workspace} notify={notify} />}</main>{toast && <div className="toast"><Icon>check_circle</Icon>{toast}</div>}</div></div>
}
