import { test, type Page } from '@playwright/test'
import { Run, loadState, settle, type Role } from '../lib'

// TEST C — field screens at 360x740 for tech1 and warehouse. Uses ids saved by the chain (state.json).
const VIEWPORT = { width: 360, height: 740 }

async function measure(run: Run, page: Page, label: string) {
  await settle(page, 600)
  const r = await page.evaluate(() => {
    const vw = window.innerWidth
    const items: { tag: string; text: string; w: number; h: number; right: number }[] = []
    document.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, summary, [role=button]').forEach(el => {
      const b = el.getBoundingClientRect(); const cs = getComputedStyle(el)
      if (!b.width || !b.height || cs.visibility === 'hidden' || (el as HTMLInputElement).type === 'hidden') return
      items.push({ tag: el.tagName.toLowerCase() + ((el as HTMLInputElement).type ? `[${(el as HTMLInputElement).type}]` : ''), text: (el.innerText || el.getAttribute('aria-label') || (el as HTMLInputElement).name || '').trim().slice(0, 30), w: Math.round(b.width), h: Math.round(b.height), right: Math.round(b.right) })
    })
    return { scrollWidth: document.documentElement.scrollWidth, vw, items }
  })
  if (r.scrollWidth > r.vw) await run.note(`${label}: horizontal scroll`, `document.scrollWidth ${r.scrollWidth} > innerWidth ${r.vw}`, page)
  const cut = r.items.filter(i => i.right > r.vw + 1)
  if (cut.length) await run.note(`${label}: controls cut off at right edge`, cut.slice(0, 6).map(i => `${i.tag} "${i.text}" right=${i.right}`).join('; '), page)
  const small = r.items.filter(i => Math.min(i.h, i.tag.includes('checkbox') || i.tag.includes('radio') ? i.w : 999) < 40 || i.h < 40)
  if (small.length) await run.note(`${label}: controls smaller than 40 px`, `${small.length} controls, e.g. ` + small.slice(0, 8).map(i => `${i.tag} "${i.text}" ${i.w}x${i.h}`).join('; '), page)
}

const SCREENS: Record<string, (s: Record<string, unknown>) => string[]> = {
  tech1: s => ['/technician/today', `/technician/surveys/${s.surveyId}`, `/technician/jobs/${s.jobId}`, `/technician/tickets/${s.ticketId}`],
  warehouse: s => ['/warehouse/dispatches', `/warehouse/dispatches/${s.dispatchId}`, '/warehouse/receiving', '/inventory'],
}

for (const role of ['tech1', 'warehouse'] as Role[]) {
  test(`C ${role} mobile 360x740`, async ({ browser }, info) => {
    const run = new Run(`C ${role} mobile`, info)
    const s = loadState()
    const { page } = await run.newRole(browser, role, { viewport: VIEWPORT })
    for (const url of SCREENS[role](s)) {
      run.step = url
      await run.check(`${role} mobile ${url}`, page, async () => { await page.goto(url); await measure(run, page, `${role} ${url}`) })
    }
    await run.finish()
  })
}
