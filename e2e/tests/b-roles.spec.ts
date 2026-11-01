import { test, type Page } from '@playwright/test'
import { Run, settle, type Role } from '../lib'

// TEST B — every sidebar link and every tab per role. Demo workspaces (/, /technician, /warehouse)
// use mock data on purpose: only crashes and console errors count there.
const DEMO = new Set(['/', '/technician', '/warehouse'])
const ROLES: Role[] = ['director', 'manager', 'office', 'warehouse', 'tech1', 'support']

async function inspect(run: Run, page: Page, label: string, demo: boolean) {
  await settle(page, 600)
  // endless spinner: still loading after 10 s
  const spinner = page.locator('.spinner:visible, .ops-spinner:visible, [role=status]:visible:has-text("Loading")')
  if (await spinner.count()) {
    await page.waitForTimeout(10_000)
    if (await spinner.count()) await run.note(`${label}: endless spinner`, `Still loading after 10 s: ${(await spinner.first().textContent())?.trim()}`, page)
  }
  const text = (await page.locator('body').innerText()).trim()
  if (text.length < 20) await run.note(`${label}: blank page`, `Body text: "${text}"`, page)
  if (/Unexpected Application Error|Error handled by React Router/.test(text)) await run.note(`${label}: crash screen`, text.slice(0, 300), page)
  if (!demo) {
    const bad = text.match(/.{0,40}\b(undefined|NaN|\[object Object\])\b.{0,40}/)
    if (bad) await run.note(`${label}: bad text on screen`, `"${bad[0].replace(/\s+/g, ' ')}"`, page)
  }
  // broken icons: Material Symbols span rendered as wide text, or an icon word in a plain span
  const broken = await page.evaluate(() => {
    const out: string[] = []
    document.querySelectorAll<HTMLElement>('.material-symbols-outlined').forEach(el => {
      const r = el.getBoundingClientRect(); const fs = parseFloat(getComputedStyle(el).fontSize)
      if (r.width > 0 && r.width > fs * 1.8) out.push(el.textContent!.trim())
    })
    document.querySelectorAll<HTMLElement>('.screen-empty > span').forEach(el => {
      if (!/Material Symbols/.test(getComputedStyle(el).fontFamily) && /^[a-z_]+$/.test(el.textContent!.trim())) out.push(el.textContent!.trim())
    })
    return [...new Set(out)]
  })
  if (broken.length) await run.note(`${label}: icon names shown as words`, broken.slice(0, 10).join(', '), page)
}

for (const role of ROLES) {
  test(`B ${role} smoke`, async ({ browser }, info) => {
    const run = new Run(`B ${role} smoke`, info)
    const { page, landing } = await run.newRole(browser, role)
    run.step = `landing ${landing}`
    await inspect(run, page, `landing ${landing}`, DEMO.has(landing))
    const nav = page.locator('aside[aria-label="Main navigation"]')
    if (!(await nav.count())) { await run.note(`${role}: no sidebar on landing page ${landing}`, 'Landing page has no navigation; collecting links from /', page); await page.goto('/'); await settle(page) }
    const links = [...new Set(await nav.locator('a[href]').evaluateAll(as => as.map(a => (a as HTMLAnchorElement).getAttribute('href')!)))]
    run.checks.push({ name: `${role} sidebar links: ${links.join(' ')}`, ok: true })
    for (const href of links) {
      run.step = href
      await run.check(`${role} open ${href}`, page, async () => {
        await page.goto(href); await settle(page)
        const path = new URL(page.url()).pathname
        await inspect(run, page, `${role} ${href}`, DEMO.has(href))
        if (!(await page.locator('aside[aria-label="Main navigation"]').count())) await run.note(`${role} ${href}: page has no sidebar/navigation`, `At ${path} the staff sidebar is missing, so the user cannot navigate or sign out`, page)
        if (DEMO.has(href)) return
        const tabs = page.locator('nav.workflow-tabs button, nav.settings-nav button')
        const n = await tabs.count()
        for (let i = 0; i < n; i++) {
          const name = (await tabs.nth(i).innerText()).trim()
          run.step = `${href} tab ${name}`
          await tabs.nth(i).click(); await settle(page)
          await inspect(run, page, `${role} ${href} tab "${name}"`, false)
        }
      })
    }
    await run.finish()
  })
}
