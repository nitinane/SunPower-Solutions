import { useState } from 'react';
import { useParams } from 'react-router-dom';
import type { TicketRead, UserBrief, Page_ProductRead_ } from './contracts';
import { Page, Card, Input, Scanner, State, Pager, useLoad, useAction, ActionState, today, money, date } from './ui';
export function AssignTicket({ id, disabled }: {
    id: number;
    disabled: boolean;
}) { const users = useLoad<UserBrief[]>('/users?role=technician'); const a = useAction(); const [tech, setTech] = useState(''), [day, setDay] = useState(today()); return <><State q={users} empty={!users.data?.length}/><ActionState action={a}/><label>Technician<select disabled={disabled || a.isPending} value={tech} onChange={e => setTech(e.target.value)}><option value="">Choose technician</option>{users.data?.map(u => <option value={u.id} key={u.id}>{u.full_name}</option>)}</select></label><Input label="Visit date" type="date" value={day} disabled={disabled || a.isPending} onChange={e => setDay(e.target.value)}/><button className="ops-primary" disabled={disabled || a.isPending || !tech || !day} onClick={() => a.mutate({ path: `/tickets/${id}/assign`, body: { technician_id: Number(tech), visit_date: day } })}>Assign visit</button></>; }
export function TicketPage({ technician = false }: {
    technician?: boolean;
}) {
    const { id } = useParams();
    const path = `/tickets/${id}`;
    const q = useLoad<TicketRead>(path);
    const a = useAction();
    const [search, setSearch] = useState(''), [page, setPage] = useState(1), [product, setProduct] = useState(''), [qty, setQty] = useState('1'), [parts, setParts] = useState<{
        product_id: number;
        qty: string;
        name: string;
    }[]>([]), [notes, setNotes] = useState(''), [hours, setHours] = useState('0'), [name, setName] = useState(''), [confirmed, setConfirmed] = useState(true), [note, setNote] = useState('');
    const d = q.data;
    const assigned = d?.status === 'assigned';
    const products = useLoad<Page_ProductRead_>(`/products?requires_serial=false&search=${encodeURIComponent(search)}&page=${page}`, assigned);
    const selected = products.data?.items.find(p => String(p.id) === product);
    return <Page title="Repair ticket"><State q={q}/><ActionState action={a}/>{d && <><Card><h2>{d.ticket_number} · {d.status}</h2><p>{d.issue_description}</p><span className="ops-status">{d.coverage_label}</span><p>Priority {d.priority} · Visit {date(d.visit_date)} · Opened {date(d.opened_at)}</p><p>Parts {money(d.parts_subtotal)} · Labour {money(d.labour_amount)} · GST {money(d.gst)} · Total {money(d.total)}</p>{d.charges.map(c => <p key={c.id}>{c.description ?? c.charge_type} · {c.quantity} · {money(c.amount)} · {c.covered_by_warranty ? 'Covered' : 'Billable'}</p>)}</Card>{!technician && d.status === 'open' && <Card><h2>Assign visit</h2><AssignTicket id={d.id} disabled={a.isPending}/></Card>}{assigned && <Card><fieldset disabled={a.isPending}><h2>Replace unit</h2>{d.faulty_serial_unit_id ? <Scanner disabled={a.isPending} onScan={new_serial => a.mutateAsync({ path: `${path}/replace-unit`, body: { new_serial } })}/> : <p>This ticket is not about a serialized unit.</p>}<h2>Resolve repair</h2><Input label="Search bulk parts" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}/><State q={products} empty={!products.data?.items.length}/><label>Part<select value={product} onChange={e => setProduct(e.target.value)}><option value="">Choose part</option>{products.data?.items.map(p => <option value={p.id} key={p.id}>{p.name} · Stock {p.in_stock} · {money(p.sale_price)} · GST {p.gst_percent}%</option>)}</select></label>{products.data && <Pager page={page} set={setPage} total={products.data.total} size={20}/>}<Input label="Part quantity" type="number" min="0.001" step="any" value={qty} onChange={e => setQty(e.target.value)}/><button className="ops-secondary" disabled={!selected || Number(qty) <= 0 || Number(qty) > Number(selected?.in_stock ?? '0') || parts.length >= 100} onClick={() => { if (selected) {
        setParts(v => [...v, { product_id: selected.id, qty, name: selected.name }]);
        setProduct('');
    } }}>Add part</button>{parts.map((p, i) => <p key={i}>{p.name} × {p.qty} <button onClick={() => setParts(v => v.filter((_, j) => j !== i))}>Remove</button></p>)}<Input label="Work notes" required maxLength={5000} value={notes} onChange={e => setNotes(e.target.value)}/><Input label="Labour hours" type="number" min="0" step="any" value={hours} onChange={e => setHours(e.target.value)}/><button className="ops-primary" disabled={a.isPending || !notes.trim() || !hours || Number(hours) < 0} onClick={() => a.mutate({ path: `${path}/resolve`, body: { work_notes: notes.trim(), labour_hours: hours, parts: parts.map(({ product_id, qty }) => ({ product_id, qty })) } })}>Resolve ticket</button></fieldset></Card>}{!technician && d.status === 'resolved' && <Card><h2>Customer confirmation</h2><Input label="Customer name" value={name} onChange={e => setName(e.target.value)}/><label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/> Customer confirms resolution (uncheck to reopen)</label><Input label="Confirmation note" value={note} maxLength={5000} onChange={e => setNote(e.target.value)}/><button className="ops-primary" disabled={a.isPending || !name.trim()} onClick={() => a.mutate({ path: `${path}/confirm`, body: { confirmed, customer_name: name.trim(), note: note || null } })}>Record confirmation</button></Card>}<Card><h2>History</h2>{!d.history.length && <p>No history yet.</p>}{d.history.map(h => <p key={h.id}>{date(h.created_at)} · {h.actor_name} · {h.action}</p>)}</Card></>}</Page>;
}
