import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch } from '../../api/client';
import { Html5Qrcode } from 'html5-qrcode';
import type { CurrentUser } from './contracts';
export const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const date = (v?: string | null) => !v ? '—' : v.length === 10 ? v : new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(v));
export function money(v: string) { const [whole, fraction = ''] = v.split('.'); return `₹${BigInt(whole).toLocaleString('en-IN')}.${fraction.padEnd(2, '0')}`; }
export function ErrorView({ error }: {
    error: unknown;
}) { const location = useLocation(); if (!error)
    return null; return <div role="alert" className="ops-form-error">{error instanceof ApiError && error.status === 401 ? <Link to="/login" state={{ from: location.pathname + location.search + location.hash }}>Sign in to continue</Link> : error instanceof ApiError && error.status === 403 ? 'You do not have access to this screen.' : error instanceof ApiError && error.status === 404 ? 'Record unavailable or not owned by you.' : error instanceof ApiError && error.status === 413 ? 'Photo is larger than 5 MB' : error instanceof ApiError && error.status === 429 ? 'Please retry later.' : error instanceof Error ? error.message : String(error)}{error instanceof ApiError && Object.entries(error.fields).map(([key, value]) => <p key={key}>{key}: {value}</p>)}</div>; }
export function Guard({ roles }: {
    roles: string[];
}) { const q = useQuery({ queryKey: ['field', 'me'], queryFn: () => apiFetch<CurrentUser>('/auth/me') }); return q.isPending ? <p role="status">Loading session…</p> : q.error ? <ErrorView error={q.error}/> : q.data.role === 'admin' || roles.includes(q.data.role) ? <Outlet /> : <p role="alert">You do not have access to this screen.</p>; }
export function Page({ title, children }: {
    title: string;
    children: ReactNode;
}) { return <main data-field className="ops-shell" style={{ display: 'block', minWidth: 0, overflowWrap: 'anywhere' }}><style>{`[data-field] button,[data-field] select,[data-field] input { min-height:44px; max-width:100%; } [data-field] select,[data-field] textarea { width:100%; box-sizing:border-box; } [data-field] fieldset { min-width:0; border:0; padding:0; } [data-field] input { max-width:100%; } [data-field] a { display:inline-flex; align-items:center; min-height:44px; max-width:100%; overflow-wrap:anywhere; } [data-field] input[type=checkbox],[data-field] input[type=radio] { width:44px; height:44px; vertical-align:middle; flex-shrink:0; } [data-field] canvas { max-width:100%; height:auto; } [data-field] button:disabled { opacity:.5; }`}</style><header className="ops-page-header"><h1>{title}</h1></header><section className="ops-content" style={{ paddingTop: 20 }}>{children}</section></main>; }
export function Card({ children }: {
    children: ReactNode;
}) { return <article className="detail-card" style={{ minWidth: 0 }}>{children}</article>; }
export function useLoad<T>(path: string, enabled = true) { return useQuery({ queryKey: ['field', path], queryFn: () => apiFetch<T>(path), enabled }); }
export function useAction<T = unknown>() { const client = useQueryClient(); return useMutation({ mutationFn: ({ path, body, method = 'POST' }: {
        path: string;
        body?: unknown;
        method?: string;
    }) => apiFetch<T>(path, { method, ...(body === undefined ? {} : { body: body instanceof FormData ? body : JSON.stringify(body) }) }), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['field'] }); } }); }
export function ActionState({ action }: {
    action: {
        error: unknown;
        isPending: boolean;
        isSuccess: boolean;
    };
}) { return <><ErrorView error={action.error}/>{action.isPending && <p role="status">Saving…</p>}{action.isSuccess && <p className="ops-notice" role="status">Saved successfully. State refreshed.</p>}</>; }
export function State({ q, empty = false }: {
    q: {
        isPending: boolean;
        error: unknown;
        refetch: () => unknown;
    };
    empty?: boolean;
}) { return q.isPending ? <p role="status">Loading…</p> : q.error ? <><ErrorView error={q.error}/><button className="ops-secondary" onClick={() => q.refetch()}>Retry</button></> : empty ? <p>No records. Adjust filters or return after work is assigned.</p> : null; }
export function Pager({ page, total, size, set }: {
    page: number;
    total: number;
    size: number;
    set: (p: number) => void;
}) { return <div className="ops-pagination"><button disabled={page === 1} onClick={() => set(page - 1)}>Previous</button><span>{page} · {total} records</span><button disabled={page * size >= total} onClick={() => set(page + 1)}>Next</button></div>; }
export function Input({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & {
    label: string;
}) { return <label style={{ display: 'grid', gap: 6, marginBottom: 12 }}>{label}<input {...props} style={{ minWidth: 0, width: '100%', boxSizing: 'border-box', minHeight: 44, padding: 8 }}/></label>; }
export function Scanner({ onScan, disabled = false }: {
    onScan: (v: string) => Promise<unknown>;
    disabled?: boolean;
}) {
    const id = 'scanner' + useId().replace(/:/g, '');
    const camera = useRef<Html5Qrcode | null>(null);
    const busy = useRef(false);
    const [serial, setSerial] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState<unknown>();
    const [running, setRunning] = useState(false);
    const input = useRef<HTMLInputElement>(null);
    const latest = useRef({ onScan, disabled });
    latest.current = { onScan, disabled };
    useEffect(() => () => { const c = camera.current; if (c?.isScanning)
        void c.stop().catch(() => { }); }, []);
    async function scan(v: string) { if (busy.current || latest.current.disabled || !v.trim())
        return; busy.current = true; setError(undefined); try {
        await latest.current.onScan(v.replace(/\s/g, '').toUpperCase());
        setMessage(`✓ ${v}`);
        setSerial('');
    }
    catch (e) {
        setError(e);
        setMessage('');
    }
    finally {
        busy.current = false;
        input.current?.focus();
    } }
    return <div><div id={id} style={{ maxWidth: '100%' }}/><div className="ops-toolbar"><button type="button" className="ops-secondary" disabled={disabled} onClick={async () => { try {
        if (running) {
            await camera.current?.stop();
            setRunning(false);
        }
        else {
            camera.current = new Html5Qrcode(id);
            await camera.current.start({ facingMode: 'environment' }, { fps: 5, qrbox: 200 }, v => { void scan(v); }, () => { });
            setRunning(true);
        }
    }
    catch (e) {
        setError(new Error(`Camera unavailable: ${String(e)}. Enter the serial below.`));
    } }}>{running ? 'Stop camera' : 'Use camera'}</button></div><form onSubmit={e => { e.preventDefault(); void scan(serial); }}><label>Serial number<input ref={input} value={serial} disabled={disabled} onChange={e => setSerial(e.target.value)} style={{ width: '100%', boxSizing: 'border-box', minHeight: 44 }}/></label><button className="ops-secondary" disabled={disabled || !serial.trim()}>Scan serial</button></form><p role="status">{message}</p><ErrorView error={error}/></div>;
}
