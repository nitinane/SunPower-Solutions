import { test, expect } from '@playwright/test'
import { uiLogin, type Role } from '../lib'

test('director notifications show API counts and quick scan focuses support search', async ({ page }) => {
  await uiLogin(page, 'director')
  await page.goto('/')
  await page.getByRole('button', { name: 'Notifications', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Operational notifications' })
  const surveys = await page.request.get('/api/v1/surveys?status=submitted&page_size=1')
  expect(surveys.ok()).toBeTruthy()
  const count = (await surveys.json()).total
  await expect(panel.getByRole('link', { name: `Surveys waiting for approval: ${count}`, exact: true })).toHaveAttribute('href', '/director/surveys')
  await expect(panel).not.toContainText('Unavailable')
  await expect(panel.getByRole('link', { name: /Unscheduled jobs: \d+/ })).toBeVisible()
  await expect(panel.getByRole('link', { name: /Pick lists waiting: \d+/ })).toBeVisible()
  await expect(panel.getByRole('link', { name: /Open tickets: \d+/ })).toBeVisible()
  await page.getByRole('button', { name: 'Help', exact: true }).click()
  const help = page.getByRole('region', { name: 'Your screens' })
  await expect(help.getByRole('link', { name: 'Office Sales', exact: true })).toBeVisible()
  await expect(help.getByRole('link', { name: 'Survey Review', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Quick Scan' }).click()
  await expect(page).toHaveURL(/\/support\?focus=search$/)
  await expect(page.getByLabel('Phone, name or serial')).toBeFocused()
})

test('warehouse quick scan opens dispatches', async ({ page }) => {
  await uiLogin(page, 'warehouse')
  await page.goto('/warehouse')
  await page.getByRole('link', { name: 'Quick Scan' }).click()
  await expect(page).toHaveURL(/\/warehouse\/dispatches$/)
})

test('technician settings has profile and sign out without staff directory', async ({ page }) => {
  await uiLogin(page, 'tech1')
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Current profile' })).toBeVisible()
  await expect(page.locator('.settings-nav').getByRole('button', { name: 'Users', exact: true })).toHaveCount(0)
  await expect(page.locator('.settings-nav').getByRole('button', { name: 'Preferences', exact: true })).toHaveCount(0)
  await page.locator('.settings-form').getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
})

test('surveyor can reach their surveys through the sidebar', async ({ page }) => {
  await uiLogin(page, 'surveyor' as Role)
  await page.getByRole('link', { name: 'My Surveys', exact: true }).click()
  await expect(page).toHaveURL(/\/surveyor\/surveys$/)
  await expect(page.getByRole('heading', { name: 'My surveys', exact: true })).toBeVisible()
  await expect(page.locator('body')).not.toContainText('You do not have access')
})
