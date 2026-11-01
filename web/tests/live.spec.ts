import { expect, test, type Page } from '@playwright/test'

const SHOTS = 'test-results/staging'
const REPORT = '../data/reports/report-0106.pdf'
const FALLBACK: Record<string, string> = { 'Lift ID': 'ELV-0106', Location: '115 Chapel Row, Fairholm', 'Inspection date': '2026-09-02', Technician: 'Luis Campos' }

test.use({ viewport: { width: 1440, height: 1000 }, actionTimeout: 60_000 })

const shot = (page: Page, name: string) => page.screenshot({ path: `${SHOTS}/${name}.png`, mask: [page.locator('p.user'), page.locator('.avatar'), page.getByText(/^Approved by/)], maskColor: '#CBD9F0' })

async function act(page: Page, action: () => Promise<unknown>) {
  const answer = page.waitForResponse((response) => new URL(response.url()).pathname.endsWith('/review'), { timeout: 120_000 })
  await action()
  expect((await answer).ok()).toBe(true)
}

async function send(page: Page, file?: string) {
  await page.getByRole('button', { name: 'New chat' }).click()
  if (!file) return page.getByRole('button', { name: 'Try a sample scanned report' }).click()
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Attach a PDF report' }).click()
  await (await chooser).setFiles(file)
  await page.getByRole('button', { name: 'Send' }).click()
}

async function draft(page: Page, file?: string) {
  await send(page, file)
  const heading = page.locator('h2[id^="lines-"]')
  await expect(heading).toBeVisible({ timeout: 240_000 })
  return (await heading.getAttribute('id'))?.slice('lines-'.length)
}

async function resolve(page: Page) {
  for (const [name, fallback] of Object.entries(FALLBACK)) {
    const field = page.locator('.fields label').filter({ hasText: name }), input = field.locator('input')
    if (!(await field.locator('.flag').count())) continue
    const value = await input.inputValue()
    for (const typed of value ? [`${value}.`, value] : [fallback]) {
      await act(page, async () => (await input.fill(typed), await input.press('Enter')))
      await expect(input).toHaveValue(typed)
    }
  }
  for (let round = 0; round < 40; round++) {
    const flagged = page.locator('tbody tr').filter({ has: page.locator('.flag') }).first()
    if (!(await flagged.count())) return
    const n = (await flagged.locator('td').first().innerText()).trim()
    const remove = page.getByRole('button', { name: `Remove line ${n}`, exact: true }), row = page.locator('tbody tr').filter({ has: remove })
    const accept = row.getByRole('button', { name: `Accept line ${n}`, exact: true }), choose = row.locator('.candidates button[aria-pressed="false"]').first()
    const flag = row.locator('td').nth(6), before = await flag.innerText()
    const target = (await accept.getAttribute('aria-disabled')) === 'false' ? accept : (await choose.count()) ? choose : remove
    await act(page, () => target.click())
    await expect(flag).not.toHaveText(before)
  }
}

test('a signed-in estimator uses every Must in the deployed web, with the final state on screen', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Turn an inspection report into a priced quote you can trust.')).toBeVisible({ timeout: 300_000 })
  await shot(page, '01-signed-in')
  await send(page, 'package.json')
  await expect(page.getByText('the file is not a PDF')).toBeVisible()
  await shot(page, '02-refused-file')
  await draft(page)
  await shot(page, '03-scanned-draft')
  const id = await draft(page, REPORT)
  if (!(await page.locator('.flag').count())) expect((await page.request.delete(`/api/quotes/${id}`)).ok()).toBe(true), await draft(page, REPORT)
  await expect(page.locator('.flag').first()).toBeVisible()
  await shot(page, '04-draft-with-flags')
  await resolve(page)
  await shot(page, '05-flags-resolved')

  let line = ''
  for (const box of await page.getByLabel(/^Quantity for line \d+$/).all()) if (!line && Number(await box.inputValue()) >= 2) line = (await box.getAttribute('aria-label'))?.split(' ').pop() ?? ''
  expect.soft(line, 'a line with a quantity of 2 or more to correct').not.toBe('')
  const quantity = page.getByLabel(`Quantity for line ${line}`, { exact: true }), card = page.getByRole('region', { name: 'Proposed correction' })
  const wanted = line ? String(Number(await quantity.inputValue()) - 1) : ''
  if (line) await page.getByLabel('Message Elevant').fill(`line ${line}, ${wanted} units`), await page.getByLabel('Message Elevant').press('Enter')
  await expect.soft(card).toBeVisible({ timeout: 90_000 })
  if (await card.isVisible()) {
    await card.scrollIntoViewIfNeeded(); await shot(page, '06-correction-proposed')
    await act(page, () => page.getByRole('button', { name: 'Confirm' }).click())
    await expect.soft(quantity).toHaveValue(wanted)
  }

  await page.getByRole('button', { name: 'Good draft' }).click()
  await expect(page.getByText('Thanks for the rating.')).toBeVisible()
  const approve = page.getByRole('button', { name: 'Approve', exact: true })
  await expect(approve).toHaveAttribute('aria-disabled', 'false')
  await approve.click()
  await expect(page.getByRole('heading', { name: 'Approved' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: /^Remove line/ })).toHaveCount(0)
  await shot(page, '07-approved-read-only')
  const download = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download quote (.docx)' }).click()
  await (await download).saveAs('test-results/live-quote.docx')
})
