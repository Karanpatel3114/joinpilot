import { expect, test } from '@playwright/test'

test('from raw ERP tables to an approved, checked data model', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('New project name').fill(`E2E ${Date.now()}`)
  await page.getByRole('button', { name: /create project/i }).click()

  await page.getByRole('button', { name: /load erp sample/i }).click()
  const tables = page.getByRole('navigation', { name: 'Tables' })
  await expect(tables.getByRole('button', { name: /BSID/ })).toBeVisible({ timeout: 30_000 })
  await tables.getByRole('button', { name: /BSID/ }).click()
  await expect(page.getByText('BSID.KUNNR → KNA1.KUNNR')).toBeVisible()

  await page.getByRole('tab', { name: 'Runs' }).click()
  await page.getByRole('button', { name: /start run/i }).click()
  await expect(page.getByRole('list', { name: 'Run steps' })).toBeVisible()
  const approve = page.getByRole('button', { name: /approve \d+ joins?/i })
  await expect(approve).toBeVisible({ timeout: 30_000 })
  await expect(page.getByLabel('Join graph')).toBeVisible()
  await approve.click()

  const sql = page.getByRole('region', { name: 'Generated SQL' })
  await expect(sql.getByText('v_bsid', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('region', { name: 'Check results' }).getByText(/(\d+) of \1 passed/)).toBeVisible()
})
