import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function audit(page: Page) {
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG).analyze()
  expect(violations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target).join(' ')}`)).toEqual([])
}

async function tabTo(page: Page, target: Locator) {
  for (let step = 0; step < 200; step++) {
    if (await target.evaluate((element) => element === document.activeElement)) return
    await page.keyboard.press('Tab')
  }
  throw new Error(`${target} cannot be reached with Tab`)
}

async function press(page: Page, target: Locator, key = 'Enter') {
  await tabTo(page, target)
  await page.keyboard.press(key)
}

test('by keyboard alone an estimator uploads, reviews, approves and downloads, and axe finds nothing', async ({ page, request }) => {
  for (const { id } of await (await request.get('/api/quotes')).json()) await request.delete(`/api/quotes/${id}`)
  await page.goto('/')
  await expect(page.getByText('Turn an inspection report into a priced quote you can trust.')).toBeVisible()
  for (const name of ['Upload an inspection report', 'Try a sample scanned report', 'Open quotes in review'])
    await expect(page.getByRole('button', { name })).toBeVisible()
  await audit(page)

  const chooser = page.waitForEvent('filechooser')
  await press(page, page.getByRole('button', { name: 'Attach a PDF report' }))
  await (await chooser).setFiles('../data/reports/report-0134.pdf')
  await press(page, page.getByRole('button', { name: 'Send' }))
  const approve = page.getByRole('button', { name: 'Approve' })
  await expect(approve).toHaveAttribute('aria-disabled', 'true')
  await expect(page.getByText('Matching 12 defects…')).toBeVisible()
  await audit(page)

  await tabTo(page, page.getByLabel('Quantity for line 2'))
  await page.keyboard.press('ControlOrMeta+a')
  await page.keyboard.type('2')
  await page.keyboard.press('Enter')
  await expect(page.locator('tbody tr').nth(1)).toContainText('€37.00')
  await press(page, page.getByRole('button', { name: 'Accept line 4' }))
  await expect(page.getByRole('button', { name: 'Accept line 4' })).toHaveAttribute('aria-disabled', 'true')
  for (const line of [1, 3, 6, 8, 9]) {
    await press(page, page.getByRole('button', { name: new RegExp(`for line ${line}$`) }).first())
    await expect(page.locator('tbody tr').nth(line - 1)).not.toContainText('Ambiguous')
  }

  await press(page, page.getByLabel('Message Elevant'))
  await page.keyboard.type('line 3, 2 units')
  await page.keyboard.press('Enter')
  await expect(page.getByText('no change found; name the line and the item or quantity it should have')).toBeVisible()
  await page.route('**/corrections', (route) => route.fulfill({ json: [{ action: 'quantity', line: 3, quantity: 2 }] }))
  await press(page, page.getByLabel('Message Elevant'))
  await page.keyboard.type('line 3, 2 units')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('region', { name: 'Proposed correction' })).toContainText('Line 3: quantity 2')
  await expect(page.getByLabel('Quantity for line 3')).toHaveValue('1')
  await press(page, page.getByRole('button', { name: 'Confirm' }))
  await expect(page.getByLabel('Quantity for line 3')).toHaveValue('2')
  await press(page, page.getByRole('button', { name: 'Good draft' }))
  await expect(page.getByText('Thanks for the rating.')).toBeVisible()
  await audit(page)

  await expect(approve).toHaveAttribute('aria-disabled', 'false')
  await press(page, approve)
  await expect(page.getByRole('heading', { name: 'Approved' })).toBeVisible()
  await audit(page)
  const download = page.waitForEvent('download')
  await press(page, page.getByRole('link', { name: 'Download quote (.docx)' }))
  expect((await download).suggestedFilename()).toMatch(/^q-[0-9a-f]{16}\.docx$/)
})
