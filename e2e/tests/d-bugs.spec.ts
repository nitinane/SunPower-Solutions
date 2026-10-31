import { test, expect, type Page } from '@playwright/test'
import { uiLogin, settle, type Role } from '../lib'

async function openAs(page: Page, role: Role, path: string) {
  await uiLogin(page, role)
  await page.goto(path)
  await settle(page)
}

test('BUG-001 all planned jobs appear regardless of order status', async ({ page }) => {
  await openAs(page, 'manager', '/manager/schedule')
  const response = await page.request.get('/api/v1/installation-jobs?status=planned&page_size=100')
  expect(response.ok()).toBeTruthy()
  const jobs = (await response.json()).items
  expect(jobs.length).toBeGreaterThan(0)
  for (const job of jobs.slice(0, 20)) {
    await expect(page.getByLabel('Planned installation job').locator(`option[value="${job.job_id}"]`)).toContainText(job.order_number)
  }
})

test('BUG-002 invoice opens with a printable address', async ({ page }) => {
  await openAs(page, 'office', '/office/invoices')
  await page.locator('.record-card .text-button').first().click()
  await expect(page.getByRole('button', { name: 'Print / Save PDF' })).toBeVisible()
  await expect(page.locator('.print-sheet')).toContainText('Hyderabad')
})

test('BUG-003 customer and repairs search show names and phones', async ({ page }) => {
  await openAs(page, 'office', '/customers')
  await page.getByLabel('Search customers').fill('9123456780')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Test Customer' })).toBeVisible()
  await page.goto('/office/repairs')
  await page.getByLabel('Customer phone / name').fill('9123456780')
  await page.getByRole('button', { name: 'Search customer' }).click()
  await expect(page.locator('.record-card strong').filter({ hasText: 'Test Customer' })).toContainText('9123456780')
})

for (const [role, target] of Object.entries({ tech1: '/technician/today', warehouse: '/warehouse/dispatches', manager: '/manager/schedule', office: '/office/enquiries', director: '/director/overview', support: '/support' })) {
  test(`BUG-004 ${role} login opens its real work screen`, async ({ page }) => {
    expect(await uiLogin(page, role as Role)).toBe(target)
    await expect(page.locator('body')).not.toContainText('Unexpected Application Error')
  })
}

test('BUG-005 field pages have navigation and sign out', async ({ page }) => {
  await openAs(page, 'manager', '/manager/schedule')
  await expect(page.locator('aside[aria-label="Main navigation"]')).toBeVisible()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401)
})

test('BUG-006 installations default schedule range is valid', async ({ page }) => {
  await uiLogin(page, 'office')
  const response = page.waitForResponse(r => r.url().includes('/api/v1/schedule?'))
  await page.goto('/installations')
  expect((await response).status()).toBe(200)
  await expect(page.locator('body')).not.toContainText('Pick at most 62 days')
})

test('BUG-007 new share URL survives clipboard denial', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('Clipboard denied')) } }))
  await openAs(page, 'director', '/director/sharing')
  await page.getByRole('button', { name: 'Create & copy link' }).click()
  await expect(page.getByLabel('New share URL')).toHaveValue(/\/share\//)
  await expect(page.getByText('Copy unavailable. Select and copy the URL above.')).toBeVisible()
  expect(errors).toEqual([])
})

test('BUG-008 public pages have no staff sidebar or session request', async ({ page }) => {
  const requests: string[] = []
  page.on('request', r => { if (r.url().includes('/auth/me')) requests.push(r.url()) })
  await page.goto('/public')
  await settle(page)
  await expect(page.locator('aside[aria-label="Main navigation"]')).toHaveCount(0)
  await page.goto('/share/invalid-token')
  await settle(page)
  await expect(page.locator('aside[aria-label="Main navigation"]')).toHaveCount(0)
  expect(requests).toEqual([])
})
