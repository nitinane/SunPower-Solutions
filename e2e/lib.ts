import { expect, request, type APIRequestContext, type Browser, type BrowserContext, type Page, type TestInfo } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

export const BASE = process.env.E2E_BASE_URL || 'http://localhost:5173'
export const PASSWORD = process.env.DEMO_PASSWORD || 'SunPower@2026'
// Admin and surveyor are created by scripts.seed, rather than seed_demo.
const passwordFor = (role: string) => ['admin', 'surveyor'].includes(role) ? process.env.SEED_PASSWORD || 'SunPower@2026' : PASSWORD
export const ROOT = path.resolve(__dirname, '..')
export const ART = path.join(__dirname, 'artifacts')
const STATE = path.join(__dirname, 'state.json')
fs.mkdirSync(ART, { recursive: true })

export type Role = 'director' | 'manager' | 'office' | 'warehouse' | 'tech1' | 'tech2' | 'support'
export const email = (role: Role) => `${role}@sunpower.in`

// ---------- shared chain state (e2e/state.json) ----------
export type ChainState = Record<string, string | number | boolean | null | undefined>
export function loadState(): ChainState { try { return JSON.parse(fs.readFileSync(STATE, 'utf8')) } catch { return {} } }
export function saveState(patch: ChainState) { const s = { ...loadState(), ...patch }; fs.writeFileSync(STATE, JSON.stringify(s, null, 2)); return s }
export function resetState() { fs.writeFileSync(STATE, '{}') }

// ---------- read-only DB access for test setup ----------
export function sql(query: string): string {
  return execFileSync('docker', ['compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.dev.yml', 'exec', '-T', 'db',
    'psql', '-U', 'sunpower', '-d', 'sunpower', '-At', '-c', query], { cwd: ROOT, encoding: 'utf8' }).trim()
}

// ---------- IST dates ----------
export function istDate(offsetDays = 0) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(Date.now() + offsetDays * 86_400_000))
}

// ---------- small valid PNG ----------
const CRC = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0 })
function crc32(buf: Buffer) { let c = 0xffffffff; for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0 }
function chunk(type: string, data: Buffer) { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td)); return Buffer.concat([len, td, crc]) }
export function makePng(w = 64, h = 64): Buffer {
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2
  const raw = Buffer.alloc((w * 3 + 1) * h)
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const o = y * (w * 3 + 1) + 1 + x * 3; raw[o] = 240; raw[o + 1] = (x * 4) & 255; raw[o + 2] = (y * 4) & 255 }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))])
}

// ---------- recorder ----------
type Event = { kind: 'console' | 'pageerror' | 'api'; who: string; url: string; text: string; status?: number; method?: string; expected?: boolean; step: string }
type Check = { name: string; ok: boolean; detail?: string; screenshot?: string; url?: string }
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60)

export class Run {
  events: Event[] = []
  checks: Check[] = []
  notes: { name: string; detail: string; url?: string; screenshot?: string }[] = []
  contexts: BrowserContext[] = []
  step = 'setup'
  private expected: { re: RegExp; status: number }[] = []
  constructor(public name: string, public info?: TestInfo) {}

  watch(page: Page, who: string) {
    page.on('console', msg => { if (msg.type() !== 'error') return; const text = msg.text().slice(0, 600); this.events.push({ kind: 'console', who, url: page.url(), text, step: this.step, expected: (msg.location().url.includes('/api/v1/me/pay?') && /status of 404/.test(text)) || (this.expected.length > 0 && /Failed to load resource: the server responded with a status of (409|404)/.test(text)) }) })
    page.on('pageerror', err => this.events.push({ kind: 'pageerror', who, url: page.url(), text: String(err.stack || err).slice(0, 800), step: this.step }))
    page.on('dialog', d => { this.events.push({ kind: 'console', who, url: page.url(), text: `[dialog ${d.type()}] ${d.message()}`, step: this.step, expected: true }); void d.accept() })
    page.on('response', async res => {
      if (res.status() < 400 || !res.url().includes('/api/')) return
      let body = ''
      try { body = (await res.text()).slice(0, 600) } catch { /* body gone */ }
      const method = res.request().method()
      // No pay run is the documented empty-state response, handled as null by the frontend.
      const expected = (res.status() === 404 && new URL(res.url()).pathname === '/api/v1/me/pay') || this.expected.some(e => e.status === res.status() && e.re.test(`${method} ${res.url()}`))
      this.events.push({ kind: 'api', who, url: res.url(), method, status: res.status(), text: body, expected, step: this.step })
    })
  }

  /** Run fn while API errors matching re/status are treated as intentional (business errors we trigger on purpose). */
  async expecting<T>(re: RegExp, status: number, fn: () => Promise<T>): Promise<T> {
    const e = { re, status }; this.expected.push(e)
    try { return await fn() } finally { await new Promise(r => setTimeout(r, 300)); this.expected = this.expected.filter(x => x !== e) }
  }

  /** A check never throws: it records pass/fail, screenshots on failure, and lets the test continue. */
  async check(name: string, page: Page | null, fn: () => Promise<unknown>): Promise<boolean> {
    this.step = name
    try {
      await fn()
      this.checks.push({ name, ok: true, url: page?.url() })
      return true
    } catch (err) {
      const shot = page ? await this.shot(page, name) : undefined
      const detail = String((err as Error).message || err).split('\n').filter(l => !l.includes('waiting for') && l.trim()).slice(0, 6).join(' | ').slice(0, 700)
      this.checks.push({ name, ok: false, detail, screenshot: shot, url: page?.url() })
      return false
    }
  }

  /** Record an observation that is a problem but not an exception (e.g. missing field). */
  async note(name: string, detail: string, page?: Page) {
    const shot = page ? await this.shot(page, name) : undefined
    this.notes.push({ name, detail, url: page?.url(), screenshot: shot })
  }

  async shot(page: Page, name: string) {
    const file = `${slug(this.name)}-${slug(name)}.png`
    try { await page.screenshot({ path: path.join(ART, file), fullPage: true, timeout: 10_000 }); return `e2e/artifacts/${file}` } catch { return undefined }
  }

  async newRole(browser: Browser, role: Role | null, opts: { viewport?: { width: number; height: number } } = {}) {
    const ctx = await browser.newContext({ baseURL: BASE, viewport: opts.viewport, hasTouch: !!opts.viewport && opts.viewport.width < 500, permissions: ['clipboard-read', 'clipboard-write'] })
    this.contexts.push(ctx)
    const page = await ctx.newPage()
    this.watch(page, role ?? 'anonymous')
    let landing = ''
    if (role) landing = await uiLogin(page, role)
    return { ctx, page, landing }
  }

  save() {
    fs.writeFileSync(path.join(ART, `log-${slug(this.name)}.json`), JSON.stringify({ name: this.name, checks: this.checks, notes: this.notes, events: this.events }, null, 2))
  }

  async finish() {
    this.save()
    for (const c of this.contexts) await c.close().catch(() => {})
    const failed = this.checks.filter(c => !c.ok).map(c => `${c.name}: ${c.detail}`)
    const unexpected = this.events.filter(e => !e.expected).map(e => `${e.kind} ${e.method ?? ''} ${e.status ?? ''} ${e.url} ${e.text}`.slice(0, 300))
    expect.soft(failed, 'failed checks').toEqual([])
    expect.soft(unexpected, 'console errors / API >= 400').toEqual([])
    expect.soft(this.notes.map(n => `${n.name}: ${n.detail}`), 'observations').toEqual([])
  }
}

// ---------- login ----------
export async function uiLogin(page: Page, role: Role): Promise<string> {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email(role))
  await page.getByLabel('Password').fill(passwordFor(role))
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15_000 })
  await page.waitForLoadState('networkidle').catch(() => {})
  return new URL(page.url()).pathname
}

export async function apiAs(role: Role): Promise<APIRequestContext> {
  const ctx = await request.newContext({ baseURL: BASE })
  const res = await ctx.post('/api/v1/auth/login', { data: { email: email(role), password: passwordFor(role) } })
  if (!res.ok()) throw new Error(`API login ${role} failed: ${res.status()} ${await res.text()}`)
  return ctx
}

export async function apiJson<T = any>(ctx: APIRequestContext, method: 'GET' | 'POST' | 'DELETE', url: string, data?: unknown): Promise<T> {
  const res = await ctx.fetch(`/api/v1${url}`, { method, data, headers: method === 'POST' ? { 'Idempotency-Key': `e2e-${Date.now()}-${Math.random()}` } : undefined })
  const text = await res.text()
  if (!res.ok()) throw new Error(`${method} ${url} -> ${res.status()} ${text.slice(0, 400)}`)
  return text ? JSON.parse(text) : (undefined as T)
}

export async function settle(page: Page, ms = 400) {
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(ms)
}
