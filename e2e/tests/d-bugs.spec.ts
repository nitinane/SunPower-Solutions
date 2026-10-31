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
