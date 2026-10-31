import { expect, test, type Page } from '@playwright/test'
import { Run, apiAs, apiJson, istDate, loadState, makePng, resetState, saveState, settle, sql } from '../lib'

// TEST A — demo chain. Tests run in order and share e2e/state.json. A failed UI step is recorded,
// then the state the next step needs is prepared through the API ("state prepared via API").

const CUSTOMER = 'Test Customer'
const PHONE = '9123456780'
const ROLE_HOME: Record<string, string> = { office: '/office/enquiries', director: '/director/overview', manager: '/manager/schedule', tech1: '/technician/today', warehouse: '/warehouse/dispatches', support: '/support' }

async function checkLanding(run: Run, role: string, landing: string, page: Page) {
  if (landing !== ROLE_HOME[role]) await run.note(`${role} login lands on ${landing}`, `Expected the ${role} work screen ${ROLE_HOME[role]}, got ${landing}`, page)
}
function selectByText(page: Page, select: ReturnType<Page['locator']>, text: string | RegExp) {
  return select.locator('option').filter({ hasText: text }).first().getAttribute('value').then(v => { if (v === null) throw new Error(`No option matching ${text}`); return select.selectOption(v) })
}

test('A01 public enquiry and duplicate phone', async ({ browser }, info) => {
  resetState()
  const run = new Run('A01 public enquiry', info)
  const { page } = await run.newRole(browser, null)
  const fill = async () => {
    await page.getByLabel('Full name *').fill(CUSTOMER)
    await page.getByLabel('Phone *').fill(PHONE)
    await page.getByLabel('Email').fill('test@example.com')
    await page.getByLabel('Property address *').fill('12 Road No 5 Jubilee Hills')
    await page.getByLabel('City *').fill('Hyderabad')
    await page.getByLabel('State *').fill('Telangana')
    await page.getByLabel('PIN code *').fill('500033')
    await page.getByLabel('Property type *').selectOption('home')
    await page.getByLabel('Solar system *').selectOption('on_grid')
    await page.getByLabel('System size (kW) *').fill('3')
    await page.getByLabel(/government subsidy/).check()
    await page.getByRole('button', { name: 'Request consultation' }).click()
  }
  let ref = ''
  await run.check('submit public enquiry -> ENQ reference', page, async () => {
    await page.goto('/public'); await settle(page)
    await fill()
    const strong = page.getByText(/Reference: ENQ-/)
    await expect(strong).toBeVisible()
    ref = (await strong.textContent())!.replace('Reference: ', '').trim()
    saveState({ enquiryRef: ref })
  })
  await run.check('same phone again -> no second enquiry', page, async () => {
    await page.getByRole('button', { name: 'Submit another enquiry' }).click()
    await fill()
    await expect(page.getByText(/Reference: ENQ-/)).toBeVisible()
    const count = Number(sql(`select count(*) from enquiries where phone_e164 like '%${PHONE}'`))
    expect(count, 'enquiry rows for this phone').toBe(1)
    const ref2 = (await page.getByText(/Reference: ENQ-/).textContent())!.replace('Reference: ', '').trim()
    expect(ref2, 'second submit returns the existing reference').toBe(ref)
  })
  await run.finish()
})

test('A02 office qualifies and books survey', async ({ browser }, info) => {
  const run = new Run('A02 office inbox', info)
  const { page, landing } = await run.newRole(browser, 'office')
  await checkLanding(run, 'office', landing, page)
  const card = page.locator('article.record-card').filter({ hasText: CUSTOMER })
  await run.check('inbox shows the website enquiry (new, website, 3 kW)', page, async () => {
    await page.goto('/office/enquiries'); await settle(page)
    await page.getByLabel('Search enquiries').fill(PHONE)
    await page.getByRole('button', { name: 'Search' }).click(); await settle(page)
    await expect(card).toHaveCount(1)
    await expect(card).toContainText('new')
    await expect(card).toContainText(/website/i)
    await expect(card).toContainText(/(^|\D)3(\.0+)? kW/)
  })
  await run.check('inbox card shows subsidy request', page, async () => {
    await expect(card).toContainText(/subsidy/i, { timeout: 2000 })
  })
  await run.check('call sheet -> qualified', page, async () => {
    await card.getByText('Actions').click()
    const form = card.locator('form').filter({ has: page.getByPlaceholder('Roof sqft') })
    await form.locator('select[name=outcome]').selectOption('qualified')
    await form.getByPlaceholder('Roof sqft').fill('400')
    await form.getByPlaceholder(/Monthly bill/).fill('3000')
    await form.locator('select[name=grid]').selectOption('yes')
    await form.getByRole('button', { name: 'Save check' }).click(); await settle(page)
    await expect(card.locator('.status-chip')).toContainText('qualified')
  })
  await run.check('customer created (Customers search)', page, async () => {
    await page.goto('/customers'); await settle(page)
    await page.getByLabel('Search customers').fill(PHONE)
    await page.getByRole('button', { name: 'Search' }).click(); await settle(page)
    await expect(page.getByRole('heading', { name: CUSTOMER })).toBeVisible()
  })
  const tomorrow = istDate(1)
  const surveyOk = await run.check('book survey with tech1 tomorrow', page, async () => {
    await page.goto('/office/surveys'); await settle(page)
    await selectByText(page, page.getByLabel('Qualified enquiry'), CUSTOMER)
    await selectByText(page, page.getByLabel('Surveyor'), 'Raju Technician')
    await page.getByLabel('Visit time (IST)').fill(`${tomorrow}T10:00`)
    await page.getByRole('button', { name: 'Book survey' }).click(); await settle(page)
    await expect(page.locator('article.record-card').filter({ hasText: CUSTOMER }).filter({ hasText: 'scheduled' })).toBeVisible()
  })
  const enquiryId = Number(sql(`select id from enquiries where phone_e164 like '%${PHONE}'`))
  saveState({ enquiryId })
  if (!surveyOk) {
    const office = await apiAs('office')
    await apiJson(office, 'POST', `/enquiries/${enquiryId}/surveys`, { surveyor_id: 7, scheduled_at: new Date(`${tomorrow}T10:00:00+05:30`).toISOString() }).catch(() => {})
    await run.note('survey booking state prepared via API', 'UI booking failed; survey scheduled through POST /enquiries/{id}/surveys')
  }
  saveState({ surveyId: Number(sql(`select id from site_surveys where enquiry_id=${enquiryId} order by id desc limit 1`)) })
  await run.finish()
})

test('A03 tech1 submits survey', async ({ browser }, info) => {
  const run = new Run('A03 survey submit', info)
  const s = loadState()
  const { page, landing } = await run.newRole(browser, 'tech1')
  await checkLanding(run, 'tech1', landing, page)
  await run.check('My day lists the survey and opens it', page, async () => {
    await page.goto('/technician/today'); await settle(page)
    await page.getByRole('link', { name: new RegExp(`${CUSTOMER} · scheduled`) }).first().click()
    await expect(page).toHaveURL(new RegExp(`/technician/surveys/${s.surveyId}$`))
  })
  await run.check('survey form has a recommended kW field', page, async () => {
    await expect(page.getByLabel(/recommended/i)).toBeVisible({ timeout: 2000 })
  })
  const ok = await run.check('submit survey: south, 15°, 20 m', page, async () => {
    if (!page.url().includes('/technician/surveys/')) { await page.goto(`/technician/surveys/${s.surveyId}`); await settle(page) }
    await page.getByLabel('Roof direction').selectOption('south')
    await page.getByLabel('Roof tilt (degrees)').fill('15')
    await page.getByLabel('Cable distance (m)').fill('20')
    await page.getByLabel('Findings').fill('Recommended system: 3 kW on-grid. Clear south roof.')
    await page.getByRole('button', { name: 'Submit survey' }).click(); await settle(page)
    await expect(page.getByRole('heading', { name: /· submitted/ })).toBeVisible()
  })
  if (!ok) {
    await apiJson(await apiAs('tech1'), 'POST', `/surveys/${s.surveyId}/submit`, { roof_direction: 'south', roof_tilt_deg: '15', cable_distance_m: '20', findings: 'Recommended 3 kW' }).catch(() => {})
    await run.note('survey submit state prepared via API', 'UI submit failed')
  }
  await run.finish()
})

test('A04 director approves survey', async ({ browser }, info) => {
  const run = new Run('A04 survey approve', info)
  const s = loadState()
  const { page, landing } = await run.newRole(browser, 'director')
  await checkLanding(run, 'director', landing, page)
  const ok = await run.check('approve survey', page, async () => {
    await page.goto('/director/surveys'); await settle(page)
    const card = page.locator('article.record-card').filter({ hasText: `Survey #${s.surveyId}` })
    await expect(card).toContainText('south')
    await card.getByRole('button', { name: 'Approve survey' }).click(); await settle(page)
    expect(sql(`select status from site_surveys where id=${s.surveyId}`)).toBe('approved')
  })
  if (!ok) { await apiJson(await apiAs('director'), 'POST', `/surveys/${s.surveyId}/approve`).catch(() => {}); await run.note('survey approval state prepared via API', 'UI approve failed') }
  await run.finish()
})

test('A05 office quote -> order -> advance payment', async ({ browser }, info) => {
  const run = new Run('A05 quote order payment', info)
  const s = loadState()
  const { page } = await run.newRole(browser, 'office')
  const sheet = page.locator('section.print-sheet')
  let quoteNumber = ''
  await run.check('create quote: 3 kW on-grid + installation; parts list appears', page, async () => {
    await page.goto('/office/quotes'); await settle(page)
    await selectByText(page, page.getByLabel('Approved survey'), CUSTOMER)
    await selectByText(page, page.getByLabel('Package'), /^3 kW On-grid system/)
    await page.getByLabel('Include installation').check()
    await page.getByRole('button', { name: 'Create quote' }).click(); await settle(page)
    await expect(sheet).toBeVisible()
    await expect(sheet).toContainText('Solar inverter 3 kW')
    await expect(sheet).toContainText('Mono PERC solar panel')
    await expect(sheet).toContainText(/Installation/i)
    expect(await sheet.locator('tbody tr').count()).toBeGreaterThanOrEqual(10)
    quoteNumber = (await sheet.locator('h2').textContent())!.trim()
    saveState({ quoteNumber })
  })
  if (!quoteNumber) {
    const office = await apiAs('office')
    const q = await apiJson(office, 'POST', '/quotes', { survey_id: s.surveyId, package_id: 3, include_installation: true }).catch(() => null)
    if (q) { quoteNumber = q.quote_number; saveState({ quoteNumber }) }
    await run.note('quote state prepared via API', 'UI quote creation failed')
  }
  const qcard = page.locator('article.record-card').filter({ hasText: quoteNumber })
  await run.check('send quote', page, async () => {
    await page.reload(); await settle(page)
    await qcard.getByRole('button', { name: 'Send' }).click(); await settle(page)
    await expect(qcard.locator('.status-chip')).toHaveText('sent')
  })
  await run.check('printable quote view opens', page, async () => {
    await page.evaluate(() => { (window as any).__printed = 0; window.print = () => { (window as any).__printed++ } })
    await qcard.getByRole('button', { name: 'Details / print' }).click()
    await expect(sheet).toContainText(quoteNumber)
    await expect(sheet).toContainText(/Total/)
    await sheet.getByRole('button', { name: 'Print / Save PDF' }).click()
    expect(await page.evaluate(() => (window as any).__printed)).toBe(1)
  })
  await run.check('accept quote -> order created', page, async () => {
    await qcard.getByRole('button', { name: 'Accept & create order' }).click(); await settle(page)
    await expect(qcard.locator('.status-chip')).toHaveText('accepted')
  })
  const quoteId = Number(sql(`select id from quotes where quote_number='${quoteNumber}'`))
  let orderId = Number(sql(`select coalesce(max(id),0) from orders where quote_id=${quoteId}`))
  if (!orderId) {
    await apiJson(await apiAs('office'), 'POST', `/quotes/${quoteId}/accept`).catch(() => {})
    orderId = Number(sql(`select coalesce(max(id),0) from orders where quote_id=${quoteId}`))
    await run.note('order state prepared via API', 'UI accept failed')
  }
  const orderNumber = sql(`select order_number from orders where id=${orderId}`)
  saveState({ quoteId, orderId, orderNumber })
  const detail = page.locator('section.detail-card')
  const paid = await run.check('record advance 50000 UPI -> balance due', page, async () => {
    await page.goto('/office/orders'); await settle(page)
    await page.getByRole('button', { name: new RegExp(`${orderNumber} - ${CUSTOMER}`) }).click(); await settle(page)
    await detail.getByLabel('Amount').fill('50000')
    await detail.getByLabel('Method').selectOption('upi')
    await detail.getByLabel('Reference').fill(`UPI-E2E-${Date.now()}`)
    await detail.getByRole('button', { name: 'Record payment' }).click(); await settle(page)
    await expect(detail).toContainText(/₹\s?50,000\.00 - upi/)
    const balance = await detail.locator('p', { hasText: 'Balance' }).locator('strong').textContent()
    expect(balance, 'balance due').not.toMatch(/₹\s?0\.00$/)
  })
  if (!paid) {
    await apiJson(await apiAs('office'), 'POST', `/orders/${orderId}/payments`, { amount: '50000.00', method: 'upi', reference: `UPI-API-${Date.now()}` }).catch(() => {})
    await run.note('payment state prepared via API', 'UI payment failed')
  }
  await run.check('pick list and crew job shown as created', page, async () => {
    await expect(detail).toContainText('Pick list')
    await expect(detail).toContainText('Installation job')
  })
  await run.check('pick list / job shown readably (not raw JSON)', page, async () => {
    await expect(detail).not.toContainText('{"id"', { timeout: 1000 })
  })
  saveState({ dispatchId: Number(sql(`select coalesce(max(id),0) from dispatches where order_id=${orderId}`)), jobId: Number(sql(`select coalesce(max(id),0) from installation_jobs where order_id=${orderId}`)) })
  await run.finish()
})

test('A06 warehouse scans, sends, delivers', async ({ browser }, info) => {
  const run = new Run('A06 dispatch', info)
  const s = loadState()
  const { page, landing } = await run.newRole(browser, 'warehouse')
  await checkLanding(run, 'warehouse', landing, page)
  const wrong = sql(`select su.serial_number from serialized_units su join products p on p.id=su.product_id where p.sku='INV-1K' and su.status='in_stock' order by 1 limit 1`)
  const inv = sql(`select su.serial_number from serialized_units su join products p on p.id=su.product_id where p.sku='INV-3K' and su.status='in_stock' order by 1 limit 1`)
  const cc = sql(`select su.serial_number from serialized_units su join products p on p.id=su.product_id where p.sku='CC-MPPT-40' and su.status='in_stock' order by 1 limit 1`)
  saveState({ inverterSerial: inv, controllerSerial: cc })
  const serialBox = page.getByLabel('Serial number')
  const scan = async (serial: string) => { await serialBox.fill(serial); await page.getByRole('button', { name: 'Scan serial' }).click(); await settle(page, 600) }
  const send = page.getByRole('button', { name: 'Send dispatch' })
  await run.check('open the order dispatch from the list', page, async () => {
    await page.goto('/warehouse/dispatches'); await settle(page)
    await page.getByRole('link', { name: new RegExp(String(s.orderNumber)) }).click(); await settle(page)
    await expect(page).toHaveURL(new RegExp(`/warehouse/dispatches/${s.dispatchId}$`))
  })
  if (!page.url().endsWith(`/warehouse/dispatches/${s.dispatchId}`)) { await page.goto(`/warehouse/dispatches/${s.dispatchId}`); await settle(page) }
  await run.check('wrong-product serial -> visible error', page, async () => {
    await run.expecting(/\/scan$/, 409, () => scan(wrong))
    await expect(page.getByRole('alert').filter({ hasText: /INV-1K/ }).first()).toBeVisible()
  })
  await run.check('Send disabled while incomplete', page, async () => { await expect(send).toBeDisabled() })
  await run.check('scan correct serials -> counters complete', page, async () => {
    await scan(inv); await scan(cc)
    await expect(page.locator('.ops-related').filter({ hasText: 'Solar inverter 3 kW' })).toContainText(/1\/1(\.0+)? scanned/)
    await expect(page.locator('.ops-related').filter({ hasText: 'MPPT' })).toContainText(/1\/1(\.0+)? scanned/)
  })
  await run.check('undo one scan and re-scan it', page, async () => {
    await page.locator('.ops-related').filter({ hasText: 'MPPT' }).getByRole('button', { name: 'Undo' }).click(); await settle(page)
    await expect(page.locator('.ops-related').filter({ hasText: 'MPPT' })).toContainText(/0\/1(\.0+)? scanned/)
    await expect(send).toBeDisabled()
    await scan(cc)
    await expect(page.locator('.ops-related').filter({ hasText: 'MPPT' })).toContainText(/1\/1(\.0+)? scanned/)
  })
  const sent = await run.check('send dispatch', page, async () => {
    await expect(send).toBeEnabled(); await send.click(); await settle(page)
    await expect(page.getByRole('heading', { name: /· dispatched/ })).toBeVisible()
  })
  if (!sent) {
    const wh = await apiAs('warehouse')
    for (const serial of [inv, cc]) await apiJson(wh, 'POST', `/dispatches/${s.dispatchId}/scan`, { serial }).catch(() => {})
    await apiJson(wh, 'POST', `/dispatches/${s.dispatchId}/send`).catch(() => {})
    await run.note('dispatch send state prepared via API', 'UI send failed'); await page.reload(); await settle(page)
  }
  const delivered = await run.check('deliver to Test Customer -> warranties shown (inverter ~2y, panels ~20y)', page, async () => {
    await page.getByLabel('Receiver name').fill(CUSTOMER)
    await page.getByRole('button', { name: 'Confirm delivery' }).click(); await settle(page)
    await expect(page.getByText(/warranties created/)).toBeVisible()
    const lines = await page.locator('p', { hasText: /^Unit .*: \d{4}-\d\d-\d\d – \d{4}-\d\d-\d\d$/ }).allTextContents()
    const years = lines.map(l => { const [a, b] = l.match(/\d{4}-\d\d-\d\d/g)!; return Math.round((Date.parse(b) - Date.parse(a)) / (365.25 * 86_400_000)) })
    expect(years, 'warranty lengths in years').toContain(2)
    expect(years, 'warranty lengths in years').toContain(20)
  })
  await run.check('warranty list names the product (not only unit ids)', page, async () => {
    await expect(page.getByText(/Unit .*(inverter|panel)/i).first()).toBeVisible({ timeout: 1500 })
  })
  if (!delivered && sql(`select status from dispatches where id=${s.dispatchId}`) !== 'delivered') {
    await apiJson(await apiAs('warehouse'), 'POST', `/dispatches/${s.dispatchId}/deliver`, { receiver_name: CUSTOMER }).catch(() => {})
    await run.note('delivery state prepared via API', 'UI delivery failed')
  }
  await run.finish()
})

test('A07 manager books crew; double booking blocked', async ({ browser }, info) => {
  const run = new Run('A07 crew calendar', info)
  const s = loadState()
  const { page, landing } = await run.newRole(browser, 'manager')
  await checkLanding(run, 'manager', landing, page)
  const today = istDate(0)
  const orderSelect = page.getByLabel('Confirmed order')
  const book = async (orderNumber: string, techs: string[]) => {
    await selectByText(page, orderSelect, orderNumber); await settle(page)
    await page.getByLabel('Installation date').fill(today)
    for (const t of techs) await page.getByLabel(t).check()
    await page.getByRole('button', { name: 'Schedule job' }).click(); await settle(page)
  }
  const ok = await run.check('assign tech1 + tech2 to the new job today', page, async () => {
    await page.goto('/manager/schedule'); await settle(page)
    await book(String(s.orderNumber), ['Raju Technician', 'Kiran Technician'])
    expect(sql(`select status from installation_jobs where id=${s.jobId}`)).toBe('scheduled')
  })
  if (!ok) {
    await apiJson(await apiAs('manager'), 'POST', `/installation-jobs/${s.jobId}/schedule`, { scheduled_date: today, technician_ids: [7, 8] }).catch(e => run.note('API schedule failed', String(e)))
    await run.note('crew booking state prepared via API', `Job ${s.jobId} (${s.orderNumber}, order status ${sql(`select status from orders where id=${s.orderId}`)}) booked through POST /installation-jobs/{id}/schedule`)
  }
  await run.check('calendar shows the booked job with crew', page, async () => {
    await page.reload(); await settle(page)
    const row = page.locator('.ops-related').filter({ hasText: String(s.orderNumber) })
    await expect(row).toContainText('Raju Technician')
    await expect(row).toContainText('Kiran Technician')
  })
  await run.check('book tech1 on another job same day -> double-booking error shown', page, async () => {
    const other = sql(`select o.order_number from installation_jobs j join orders o on o.id=j.order_id where j.status='planned' and o.status='confirmed' and j.id<>${s.jobId} order by j.id limit 1`)
    expect(other, 'another bookable job exists').not.toBe('')
    await run.expecting(/\/schedule$/, 409, () => book(other, ['Raju Technician']))
    await expect(page.getByRole('alert').filter({ hasText: /already/i })).toBeVisible()
  })
  await run.finish()
})

test('A08 tech1 completes installation', async ({ browser }, info) => {
  const run = new Run('A08 installation', info)
  const s = loadState()
  const { page } = await run.newRole(browser, 'tech1')
  await run.check('My day lists the job and opens it', page, async () => {
    await page.goto('/technician/today'); await settle(page)
    await page.getByRole('link', { name: new RegExp(`${CUSTOMER} · scheduled`) }).click()
    await expect(page).toHaveURL(new RegExp(`/technician/jobs/${s.jobId}$`))
  })
  if (!page.url().endsWith(`/technician/jobs/${s.jobId}`)) { await page.goto(`/technician/jobs/${s.jobId}`); await settle(page) }
  await run.check('start installation', page, async () => {
    await page.getByRole('button', { name: 'Start installation' }).click(); await settle(page)
    await expect(page.getByRole('heading', { name: /· in_progress/ })).toBeVisible()
  })
  await run.check('upload a small PNG photo', page, async () => {
    await page.getByLabel(/Installation photos/).setInputFiles({ name: 'roof.png', mimeType: 'image/png', buffer: makePng() }); await settle(page)
    await expect(page.getByRole('link', { name: /Photo #\d+/ })).toBeVisible()
  })
  const complete = page.getByRole('button', { name: 'Complete installation' })
  await run.check('fill kW 3, power test, signer; Complete disabled with empty signature', page, async () => {
    await page.getByLabel('System kW').fill('3')
    await page.getByLabel('Power test passed').check()
    await page.getByLabel('Customer signer name').fill(CUSTOMER)
    await expect(complete).toBeDisabled()
  })
  const done = await run.check('draw signature -> complete -> completed', page, async () => {
    const pad = page.getByLabel('Customer signature pad')
    const box = (await pad.boundingBox())!
    for (let i = 0; i < 7; i++) {
      await page.mouse.move(box.x + 15, box.y + 20 + i * 22)
      await page.mouse.down()
      for (let x = 0; x <= 10; x++) await page.mouse.move(box.x + 15 + x * 21, box.y + 20 + i * 22 + (x % 2 ? 14 : -10), { steps: 3 })
      await page.mouse.up()
    }
    await expect(complete).toBeEnabled()
    await complete.click(); await settle(page)
    await expect(page.getByRole('heading', { name: /· completed/ })).toBeVisible()
  })
  if (!done) await run.note('installation not completed in UI', `job status now ${sql(`select status from installation_jobs where id=${s.jobId}`)}`, page)
  await run.finish()
})

test('A09 support search, warranty ticket loop', async ({ browser }, info) => {
  const run = new Run('A09 support ticket', info)
  const s = loadState()
  const { page, landing } = await run.newRole(browser, 'support')
  await checkLanding(run, 'support', landing, page)
  const search = async (text: string) => { await page.getByLabel('Phone, name or serial').fill(text); await page.waitForTimeout(500); await settle(page) }
  const card = page.locator('article.detail-card').filter({ has: page.getByRole('heading', { name: CUSTOMER }) })
  for (const term of [PHONE, String(s.inverterSerial), CUSTOMER]) {
    await run.check(`search "${term}" finds customer with active warranty`, page, async () => {
      if (!page.url().endsWith('/support')) { await page.goto('/support'); await settle(page) }
      await search(term)
      await expect(card).toBeVisible()
      await expect(card.locator('.ops-related').filter({ hasText: String(s.inverterSerial) }).locator('.ops-status')).toContainText('active')
    })
  }
  let ticketId = 0
  await run.check('create ticket on inverter (E-01)', page, async () => {
    await card.getByLabel('Serialized unit').selectOption({ label: `${s.inverterSerial} · Solar inverter 3 kW` })
    await card.getByLabel('Fault code (optional)').fill('E-01')
    await card.getByLabel('Issue description').fill('Inverter shows fault E-01 and shuts down at noon')
    await card.getByRole('button', { name: 'Create ticket' }).click()
    await page.waitForURL(/\/support\/tickets\/\d+$/); await settle(page)
    ticketId = Number(page.url().split('/').pop())
  })
  if (!ticketId) {
    const unit = Number(sql(`select id from serialized_units where serial_number='${s.inverterSerial}'`))
    const customer = Number(sql(`select id from customers where phone like '%${PHONE}'`).split('\n')[0] || 0)
    const t = await apiJson(await apiAs('support'), 'POST', '/tickets', { customer_id: customer, serialized_unit_id: unit, fault_code: 'E-01', issue_description: 'Inverter fault E-01', priority: 'normal' }).catch(e => { void run.note('API ticket create failed', String(e)); return null })
    ticketId = t?.id ?? 0
    await run.note('ticket state prepared via API', 'UI ticket creation failed')
  }
  saveState({ ticketId })
  const heading = page.getByRole('heading', { name: /^SR-|· / }).first()
  const assign = async (label: string) => run.check(label, page, async () => {
    await page.goto(`/support/tickets/${ticketId}`); await settle(page)
    await page.getByLabel('Technician').selectOption({ label: 'Raju Technician' })
    await page.getByRole('button', { name: 'Assign visit' }).click(); await settle(page)
    await expect(page.locator('h2').first()).toContainText('assigned')
  })
  const tech = await run.newRole(browser, 'tech1')
  const resolve = async (label: string) => run.check(label, tech.page, async () => {
    await tech.page.goto(`/technician/tickets/${ticketId}`); await settle(tech.page)
    await tech.page.getByLabel('Work notes').fill('Reset inverter, tightened DC terminals')
    await tech.page.getByLabel('Labour hours').fill('1')
    await tech.page.getByRole('button', { name: 'Resolve ticket' }).click(); await settle(tech.page)
    await expect(tech.page.locator('h2').first()).toContainText('resolved')
  })
  const confirm = async (label: string, fixed: boolean, expectStatus: string) => run.check(label, page, async () => {
    await page.goto(`/support/tickets/${ticketId}`); await settle(page)
    await page.getByLabel('Customer name').fill(CUSTOMER)
    const box = page.getByLabel(/Customer confirms resolution/)
    if (fixed) await box.check(); else await box.uncheck()
    await page.getByRole('button', { name: 'Record confirmation' }).click(); await settle(page)
    await expect(page.locator('h2').first()).toContainText(expectStatus)
  })
  await assign('assign ticket to tech1')
  await run.check('tech1 sees the repair visit in My day', tech.page, async () => {
    await tech.page.goto('/technician/today'); await settle(tech.page)
    await expect(tech.page.getByRole('link', { name: /· assigned/ }).first()).toBeVisible()
  })
  await resolve('tech1 resolves with 1 labour hour')
  await confirm('support confirms "not fixed" -> back to open', false, 'open')
  await assign('re-assign after reopen')
  await resolve('tech1 resolves again')
  await confirm('support confirms fixed -> closed', true, 'closed')
  await run.check('charges 0.00 under warranty', page, async () => {
    await expect(page.getByText(/Total ₹0\.00/)).toBeVisible()
    await expect(page.locator('.ops-status').first()).toContainText(/warranty/i)
  })
  void heading
  await run.finish()
})

test('A10 director dashboard and share link', async ({ browser }, info) => {
  const run = new Run('A10 director dashboard', info)
  const s = loadState()
  const { page } = await run.newRole(browser, 'director')
  await page.goto('/director/overview'); await settle(page)
  for (const [value, label] of [['today', 'Today'], ['week', 'This week'], ['month', 'This month']]) {
    await run.check(`dashboard ${label} shows the order in profit per job`, page, async () => {
      await page.getByLabel('Report period').selectOption(value); await settle(page)
      await expect(page.locator('section.detail-card table')).toContainText(String(s.orderNumber))
    })
  }
  let url = ''; let shareId = 0
  await run.check('create share link', page, async () => {
    await page.goto('/director/sharing'); await settle(page)
    await page.getByLabel('Period').selectOption('month')
    const [res] = await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/v1/dashboard/share') && r.request().method() === 'POST'), page.getByRole('button', { name: /Create & copy link/ }).click()])
    expect(res.status()).toBe(201)
    const body = await res.json(); url = new URL(body.url, page.url()).toString(); shareId = body.id
    await settle(page)
  })
  await run.check('new share link is visible on screen (not only copied to clipboard)', page, async () => {
    const token = url.split('/').pop()!
    await expect(page.getByText(token)).toBeVisible({ timeout: 2000 })
  })
  const anon = await run.newRole(browser, null)
  await run.check('share link opens read-only without login', anon.page, async () => {
    await anon.page.goto(url); await settle(anon.page)
    await expect(anon.page.getByRole('heading', { name: 'Operations overview' })).toBeVisible()
    await expect(anon.page.locator('.report-card').first()).toContainText(/₹|\d/)
    expect(await anon.page.locator('input, select, textarea, button, form').count(), 'interactive controls on shared page').toBe(0)
  })
  await run.check('revoke link -> link shows unavailable', page, async () => {
    const list = await apiJson(await apiAs('director'), 'GET', '/dashboard/share')
    const idx = (list.items as { id: number }[]).findIndex(x => x.id === shareId)
    expect(idx).toBeGreaterThanOrEqual(0)
    await page.getByRole('button', { name: 'Revoke link' }).nth(idx).click(); await settle(page)
    await run.expecting(/public\/dashboard/, 404, async () => { await anon.page.reload(); await settle(anon.page) })
    await expect(anon.page.getByRole('heading', { name: 'Report unavailable' })).toBeVisible()
  })
  await run.finish()
})

test('A11 office invoice printable', async ({ browser }, info) => {
  const run = new Run('A11 invoice', info)
  const s = loadState()
  const { page } = await run.newRole(browser, 'office')
  await run.check('invoices list contains the order invoice; printable view opens', page, async () => {
    await page.goto('/office/invoices'); await settle(page)
    const inv = sql(`select invoice_number from invoices where order_id=${s.orderId} order by id limit 1`)
    expect(inv, 'invoice row exists in DB').not.toBe('')
    await page.getByRole('button', { name: new RegExp(`${inv} · ${CUSTOMER}`) }).click(); await settle(page)
    const sheet = page.locator('section.print-sheet')
    await expect(sheet).toContainText('GST INVOICE')
    await expect(sheet).toContainText(inv)
    await page.evaluate(() => { (window as any).__printed = 0; window.print = () => { (window as any).__printed++ } })
    await sheet.getByRole('button', { name: 'Print / Save PDF' }).click()
    expect(await page.evaluate(() => (window as any).__printed)).toBe(1)
  })
  await run.finish()
})
