import { test, expect, type APIRequestContext } from '@playwright/test'
import { uiLogin } from '../lib'

const rupees = (value: string) => {
  const [whole, fraction = '00'] = value.split('.')
  return `₹${BigInt(whole).toLocaleString('en-IN')}.${fraction.padEnd(2, '0')}`
}
async function json(api: APIRequestContext, path: string) {
  const response = await api.get(`/api/v1${path}`)
  expect(response.ok(), path).toBeTruthy()
  return response.json()
}
async function all(api: APIRequestContext, path: string) {
  const first = await json(api, `${path}?page=1&page_size=100`)
  const items = [...first.items]
  for (let page = 2; items.length < first.total; page++) {
    items.push(...(await json(api, `${path}?page=${page}&page_size=100`)).items)
  }
  return items
}

test('owner cards, projects, approval queues and every chart month match the APIs', async ({ page }) => {
  await uiLogin(page, 'director')
  const summary = await json(page.request, '/dashboard/summary?period=month')
  const trend = await json(page.request, '/dashboard/trend?months=12')
  const orders = await json(page.request, '/orders?page_size=20')
  const surveys = await json(page.request, '/surveys?status=submitted&page_size=1')
  const jobs = await json(page.request, '/installation-jobs?status=planned&page_size=1')
  await page.goto('/')
  await expect(page.getByTestId('owner-orders').locator('.kpi-value-row strong')).toHaveText(String(summary.cards.orders_confirmed))
  await expect(page.getByTestId('owner-payments').locator('.kpi-value-row strong')).toHaveText(rupees(summary.cards.payments_received))
  await expect(page.getByTestId('owner-unfinished').locator('.kpi-value-row strong')).toHaveText(String(summary.cards.unfinished_jobs))
  await expect(page.getByTestId('owner-repairs').locator('.kpi-value-row strong')).toHaveText(String(summary.cards.open_repairs))
  const queue = page.locator('.approvals-panel')
  for (const [label, count] of [['Surveys waiting for approval', surveys.total], ['Unscheduled jobs', jobs.total], ['Open repairs', summary.cards.open_repairs]]) {
    await expect(queue.locator('.approval-card').filter({ hasText: String(label) })).toContainText(`${count} waiting`)
  }
  const active = orders.items.filter((order: { status: string }) => !['installed', 'completed', 'cancelled'].includes(order.status)).slice(0, 6)
  await expect(page.getByTestId('owner-projects').locator('.project-row')).toHaveCount(active.length)
  for (const order of active) {
    const row = page.getByTestId('owner-projects').locator('.project-row').filter({ hasText: order.order_number })
    await expect(row).toContainText(order.customer_name)
    await expect(row).toContainText(order.status.replaceAll('_', ' '))
  }
  await page.getByText('View monthly values', { exact: true }).click()
  await expect(page.locator('.live-trend-values tbody tr')).toHaveCount(12)
  for (const month of trend) {
    const row = page.locator('.live-trend-values tbody tr').filter({ hasText: month.month })
    await expect(row).toContainText(rupees(month.booked_order_value))
    await expect(row).toContainText(rupees(month.payments_received))
  }
})

test('technician workspace uses the current technician assignments', async ({ page }) => {
  await uiLogin(page, 'tech2')
  const today = await json(page.request, '/me/today')
  await page.goto('/technician')
  await expect(page.getByTestId('tech-jobs').locator('.kpi-value-row strong')).toHaveText(String(today.installation_jobs.length))
  await expect(page.getByTestId('tech-surveys').locator('.kpi-value-row strong')).toHaveText(String(today.surveys.length))
  await expect(page.getByTestId('tech-repairs').locator('.kpi-value-row strong')).toHaveText(String(today.ticket_visits.length))
  await expect(page.getByTestId('tech-queue').locator('.queue-row')).toHaveCount(today.surveys.length + today.installation_jobs.length + today.ticket_visits.length)
  for (const job of today.installation_jobs) await expect(page.getByTestId('tech-queue').locator(`a[href="/technician/jobs/${job.job_id}"]`)).toBeVisible()
  await expect(page.locator('main')).not.toContainText('JSA')
  await expect(page.locator('main')).not.toContainText('WEATHER')
})

test('warehouse stock thresholds and dispatch totals match all API pages', async ({ page }) => {
  await uiLogin(page, 'warehouse')
  const stock = await all(page.request, '/stock')
  const dispatches = await all(page.request, '/dispatches')
  const low = stock.filter(row => row.low_stock)
  await page.goto('/warehouse')
  await expect(page.getByTestId('warehouse-products').locator('.kpi-value-row strong')).toHaveText(String(stock.length))
  await expect(page.getByTestId('warehouse-low').locator('.kpi-value-row strong')).toHaveText(String(low.length))
  await expect(page.getByTestId('warehouse-waiting').locator('.kpi-value-row strong')).toHaveText(String(dispatches.filter(row => ['draft', 'packed'].includes(row.status)).length))
  await expect(page.getByTestId('warehouse-transit').locator('.kpi-value-row strong')).toHaveText(String(dispatches.filter(row => row.status === 'dispatched').length))
  await expect(page.getByTestId('warehouse-stock').locator('.queue-row')).toHaveCount(low.length)
  await page.getByRole('button', { name: 'Show all stock', exact: true }).click()
  await expect(page.getByTestId('warehouse-stock').locator('.queue-row')).toHaveCount(stock.length)
  await expect(page.getByTestId('warehouse-dispatches').locator('.queue-row')).toHaveCount(Math.min(8, dispatches.length))
})

test('guest and wrong-role workspaces offer sign-in and do not fetch protected workspace data', async ({ page }) => {
  const privateRequests: string[] = []
  page.on('request', request => { if (/\/api\/v1\/(dashboard\/(summary|trend)|orders\?|stock\?|dispatches\?|me\/today)/.test(request.url())) privateRequests.push(request.url()) })
  for (const [path, role] of [['/', 'director'], ['/technician', 'technician'], ['/warehouse', 'warehouse']]) {
    await page.goto(path)
    await expect(page.getByRole('heading', { name: `Sign in as ${role} to see live data` })).toBeVisible()
    await expect(page.locator('main').getByRole('link', { name: 'Sign in', exact: true })).toHaveAttribute('href', '/login')
  }
  expect(privateRequests).toEqual([])
  await uiLogin(page, 'office')
  privateRequests.length = 0
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sign in as director to see live data' })).toBeVisible()
  expect(privateRequests.filter(path => /dashboard\/(summary|trend)/.test(path))).toEqual([])
})

test('workspace API failure offers a working retry', async ({ page }) => {
  await uiLogin(page, 'director')
  await page.route('**/api/v1/dashboard/trend?months=12', route => route.fulfill({ status: 503, json: { error: { code: 'unavailable', message: 'Trend temporarily unavailable' } } }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Could not load live data' })).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole('alert')).toContainText('Trend temporarily unavailable')
  await page.unroute('**/api/v1/dashboard/trend?months=12')
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(page.getByTestId('owner-orders')).toBeVisible()
})
