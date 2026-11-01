import { test, expect } from '@playwright/test'
import { uiLogin, type Role } from '../lib'

test('BUG-018 surveyor login can open its profile destination', async ({ page }) => {
  expect(await uiLogin(page, 'surveyor' as Role)).toBe('/settings')
  await expect(page.getByRole('heading', { name: 'Current profile' })).toBeVisible()
  await expect(page.locator('body')).toContainText('Sameer Surveyor')
  await expect(page.getByRole('button', { name: 'Sign out', exact: true }).first()).toBeVisible()
})

test('admin login opens the director screen', async ({ page }) => {
  expect(await uiLogin(page, 'admin' as Role)).toBe('/director/overview')
  await expect(page.getByRole('heading', { name: 'Director dashboard' })).toBeVisible()
})
