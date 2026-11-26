import { type Page, expect, test } from '@playwright/test'

// Captures README screenshots from the real app: SCREENSHOTS=1 npx playwright test screenshots
test.skip(!process.env.SCREENSHOTS, 'only when refreshing README screenshots')
test.use({ viewport: { width: 1440, height: 900 }, colorScheme: 'light' })

const out = (name: string) => `../docs/images/${name}.png`

/** Full-page capture from the top, so the sticky header sits where it belongs. */
async function shot(page: Page, name: string) {
  await page.evaluate('window.scrollTo(0, 0)')
  await page.waitForTimeout(200)
  await page.screenshot({ path: out(name), fullPage: true })
}

test('README screenshots', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('New project name').fill('Demo ERP')
  await page.getByRole('button', { name: /create project/i }).click()
  await page.getByRole('button', { name: /load erp sample/i }).click()
  const tables = page.getByRole('navigation', { name: 'Tables' })
  await tables.getByRole('button', { name: /BSID/ }).click()
  await page.getByLabel('Find columns by business words').fill('customer name')
  await page.getByRole('button', { name: /search/i }).click()
  await expect(page.getByText('KNA1.NAME1').first()).toBeVisible()
  await shot(page, 'profile')

  await page.getByRole('tab', { name: 'Runs' }).click()
  await page.getByRole('button', { name: /start run/i }).click()
  await expect(page.getByRole('button', { name: /approve 5 joins/i })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('list', { name: 'Proposed joins' }).getByRole('button', { name: /BSID\.KUNNR → KNA1\.KUNNR/ }).click()
  await page.waitForTimeout(500)
  await shot(page, 'approval')

  await page.getByRole('button', { name: /approve 5 joins/i }).click()
  await expect(page.getByRole('region', { name: 'Check results' })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('region', { name: 'Generated SQL' }).scrollIntoViewIfNeeded()
  await shot(page, 'results')

  await page.getByRole('link', { name: /open the kpi dashboard/i }).click()
  await expect(page.locator('.recharts-bar-rectangle').first()).toBeVisible()
  await page.waitForTimeout(800)
  await shot(page, 'dashboard')

  await page.goto('/')
  await page.screenshot({ path: out('projects') })
})
