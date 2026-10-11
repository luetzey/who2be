import { expect, test } from '@playwright/test'

import { apiRequest, createUser, loginAs, seedWorkspace } from './helpers/auth'
import { decideCookieConsent } from './helpers/consent'
import { expectNoHorizontalScroll, measureHorizontalOverflow } from './helpers/viewport'

/**
 * Selbsttest des Scroll-Helfers (Welle 7 / K2).
 *
 * Ein Helfer, der immer gruen ist, ist wertlos — genau deshalb steht die
 * Gegenprobe hier als dauerhafter Test und nicht nur als einmaliger
 * Wegwerf-Commit im Protokoll. Ein spaeterer Umbau von
 * `helpers/viewport.ts`, der die Erkennung versehentlich entschaerft, faellt
 * damit sofort auf, statt still alle Journeys blind zu stellen.
 *
 * Die Faelle laufen gegen `page.setContent`, nicht gegen die App: geprueft
 * wird hier die Messung selbst, und die darf nicht davon abhaengen, ob gerade
 * ein Compose-Stack steht oder wie eine Route heute aussieht. Die Breiten sind
 * relativ zu `clientWidth` konstruiert, damit alle vier Playwright-Profile
 * (320px bis Desktop) denselben Fall sehen.
 */

const PAGE_SHELL = (body: string) => `<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{box-sizing:border-box}body{margin:0}</style></head>
<body>${body}</body></html>`

test('Helfer meldet ein sauberes Dokument als gruen', async ({ page }) => {
  await page.setContent(
    PAGE_SHELL('<div style="width:100%;height:200px" data-testid="ok-block">Inhalt</div>'),
  )
  await expectNoHorizontalScroll(page, 'Selbsttest: sauberes Dokument')
})

test('Rot-Probe: Helfer findet einen echten Ueberlauf UND benennt ihn', async ({ page }) => {
  await page.setContent(
    PAGE_SHELL(
      '<div style="width:100%">ok</div>' +
        '<div data-testid="overflow-culprit" class="zu-breit" ' +
        'style="width:calc(100% + 200px);height:50px">zu breit</div>',
    ),
  )

  const probe = await measureHorizontalOverflow(page)
  expect(probe.scrollWidth).toBeGreaterThan(probe.clientWidth)
  // Der Kern der Karte: nicht nur DASS etwas ueberlaeuft, sondern WAS.
  expect(probe.offenders.length).toBeGreaterThan(0)
  expect(probe.offenders[0].selector).toContain('data-testid="overflow-culprit"')
  expect(probe.offenders[0].selector).toContain('zu-breit')
  expect(probe.offenders[0].right).toBeGreaterThan(probe.clientWidth)

  // Und die Assertion selbst schlaegt an — mit dem Selektor in der Meldung.
  const failure = await expectNoHorizontalScroll(page).then(
    () => null,
    (error: Error) => error.message,
  )
  expect(failure, 'expectNoHorizontalScroll haette fehlschlagen muessen').not.toBeNull()
  expect(failure).toContain('overflow-culprit')
})

test('Kein Fehlalarm: bewusst scrollbarer Wrapper (Tabellen-Muster) bleibt gruen', async ({
  page,
}) => {
  // Exakt das Muster aus `apps/web/src/components/ui/table.tsx`: ein Wrapper
  // mit `overflow-auto` (NICHT `overflow-x-auto`) um eine Tabelle, die breiter
  // ist als der Viewport. §4.4 der Design-Sprache nimmt genau diesen Fall aus.
  await page.setContent(
    PAGE_SHELL(
      '<div class="relative w-full" style="overflow:auto">' +
        '<table data-testid="breite-tabelle" style="width:1400px">' +
        '<tr><td style="width:700px">A</td><td style="width:700px">B</td></tr>' +
        '</table></div>',
    ),
  )

  const probe = await measureHorizontalOverflow(page)
  expect(
    probe.offenders.map((o) => o.selector),
    'Tabelle in einem overflow-auto-Wrapper darf nicht als Verursacher gelten',
  ).toEqual([])
  await expectNoHorizontalScroll(page, 'Selbsttest: Tabellen-Wrapper')
})

/**
 * Mobil-Spec P1 (Befunde M1 + M12, WCAG 1.4.10 Reflow): frei eingegebene
 * Texte brechen um, statt die Seite zu verbreitern.
 *
 * Gemessen war `scrollWidth` 517 px bei 320/390/430 px auf Persona-, Agent-,
 * System-Prompt- und Playbook-Detail sowie 530 px auf der Playbook-Liste.
 * Ursache: eine lange URL ohne Trennstelle in der Beschreibung setzt die
 * min-content-Breite des Kopf-`<p>` auf ~437 px, und die Flex-Kette gibt das
 * bis zum Dokument weiter. Der Seed traegt deshalb genau so eine URL (keine
 * Bindestriche, die Chromium als Umbruchstelle nimmt) in jede Beschreibung und
 * als Trigger-Chip ins Playbook (M12, Tag-Feld auf dem Bearbeiten-Tab).
 *
 * Laeuft auf allen vier Profilen; `mobile-320` und `mobile-iphone-13` (390 px)
 * sind die scharfen Faelle. Rot-Probe: `wrap-anywhere` am Kopf-`<p>` in
 * `DetailHeader.tsx` entfernt → Persona-/Agent-/System-Prompt-Detail rot.
 */
const LONG_URL =
  'https://intranet.example.com/richtlinien/kommunikation/' +
  'feedbackkulturundgespraechsfuehrungfuerteamleitungen/2026/leitfaden_fuer_schwierige_gespraeche.pdf'
const LONG_DESCRIPTION = `Verweise auf interne Richtlinien stehen mit Titel und Abschnitt, etwa ${LONG_URL} fuer das Mitarbeitergespraech.`

function blockDoc(text: string): { blocks: unknown[] } {
  return {
    blocks: [
      {
        id: 'e2e-reflow-p1',
        type: 'paragraph',
        props: {},
        content: [{ type: 'text', text, styles: {} }],
        children: [],
      },
    ],
  }
}

test('M1/M12: lange URL ohne Trennstelle verbreitert keine Liste und keine Detailseite', async ({
  page,
  request,
}) => {
  // Zwoelf Seitenaufrufe plus Seed: das 30-s-Standardbudget reicht dafuer nicht.
  test.setTimeout(120_000)

  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const post = <T>(path: string, data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method: 'POST', data })

  const persona = await post<{ id: string }>('/personas', {
    name: 'E2E Reflow Persona',
    content: {
      description: LONG_DESCRIPTION,
      tags: ['reflow'],
      content: blockDoc('Profil'),
    },
  })
  const playbook = await post<{ id: string }>('/playbooks', {
    name: 'E2E Reflow Playbook',
    content: { description: LONG_DESCRIPTION, triggers: `gespraech vorbereiten, ${LONG_URL}` },
  })
  const resource = await post<{ id: string }>('/resources', {
    name: 'E2E Reflow Resource',
    content: { description: LONG_DESCRIPTION, blocks: blockDoc('Inhalt').blocks },
  })
  const systemPrompt = await post<{ id: string }>('/system-prompts', {
    name: 'E2E Reflow System-Prompt',
    content: {
      description: LONG_DESCRIPTION,
      body: JSON.stringify(blockDoc('Grund-Prompt').blocks),
    },
  })
  const tool = await post<{ id: string }>('/external_tools', {
    name: 'E2E Reflow Tool',
    content: { display_name: 'Reflow', fallback_note: LONG_DESCRIPTION },
  })
  const agent = await post<{ id: string }>('/agents', {
    name: 'E2E Reflow Agent',
    description: LONG_DESCRIPTION,
  })

  const ws = `/w/${workspaceId}`
  // Dritter Wert: zeigt die Seite den Seed-Text als Text? Nur dann laesst sich
  // pruefen, dass der Verursacher wirklich gerendert ist (sonst misst die
  // Probe eine Seite ohne ihn und ist blind gruen). Resource-/Tool-Detail
  // zeigen im Kopf die Version, die Beschreibung steht dort im Formularfeld;
  // die Tool-Liste zeigt keine Beschreibung.
  const routes: Array<[string, string, boolean]> = [
    [`${ws}/personas`, 'personas (Liste)', true],
    [`${ws}/personas/${persona.id}`, 'personas/:id', true],
    [`${ws}/playbooks`, 'playbooks (Liste)', true],
    [`${ws}/playbooks/${playbook.id}`, 'playbooks/:id (Bearbeiten, Trigger-Chip)', true],
    [`${ws}/resources`, 'resources (Liste)', true],
    [`${ws}/resources/${resource.id}`, 'resources/:id', false],
    [`${ws}/system-prompts`, 'system-prompts (Liste)', true],
    [`${ws}/system-prompts/${systemPrompt.id}`, 'system-prompts/:id', true],
    [`${ws}/tools`, 'tools (Liste)', false],
    [`${ws}/tools/${tool.id}`, 'tools/:id', false],
    [`${ws}/agents`, 'agents (Liste)', true],
    [`${ws}/agents/${agent.id}`, 'agents/:id', true],
  ]

  // Alle Routen messen, dann gesammelt pruefen: ein roter Lauf nennt jede
  // betroffene Seite auf einmal, nicht nur die erste.
  const failures: string[] = []
  for (const [path, label, showsSeedText] of routes) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    if (showsSeedText) {
      await expect(page.getByText(LONG_URL, { exact: false }).first()).toBeVisible()
    }
    const probe = await measureHorizontalOverflow(page)
    if (probe.scrollWidth > probe.clientWidth + 1) {
      const culprit = probe.offenders[0]?.selector ?? 'kein einzelnes Element'
      failures.push(`${label}: scrollWidth ${probe.scrollWidth} > ${probe.clientWidth} (${culprit})`)
    }
  }
  expect(failures, 'Seiten mit horizontalem Body-Scroll').toEqual([])

  // M12: Der Trigger-Chip mit der URL bleibt innerhalb des Tag-Felds.
  await page.goto(`${ws}/playbooks/${playbook.id}`)
  const chip = page.locator('span', { hasText: LONG_URL }).filter({ has: page.getByRole('button') })
  await expect(chip.first()).toBeVisible()
  const chipBox = await chip.first().boundingBox()
  const viewportWidth = page.viewportSize()?.width ?? 0
  expect(chipBox, 'Trigger-Chip ohne Bounding-Box').not.toBeNull()
  expect(chipBox!.x + chipBox!.width).toBeLessThanOrEqual(viewportWidth + 1)
})

/**
 * Mobil-Spec P5 (Befund M5): Textfelder wachsen mit dem Inhalt bis 60 svh,
 * statt innen zu scrollen (Scroll-in-Scroll). Gemessen war bei 320 px:
 * Agent-Beschreibung 16,4-fache, Tool-Fallback-Hinweis 4,8-fache innere Tiefe.
 *
 * Zwei Pfade, beide geprueft:
 * - `native`: Chromium kennt `field-sizing: content`; kein JavaScript.
 * - `fallback`: Browser ohne die Eigenschaft (Safari < 26.2, Firefox < 152)
 *   werden nachgestellt — `CSS.supports` verneint, die Eigenschaft ist per
 *   Stylesheet ausser Kraft. Dann muss `useAutoGrow` die Hoehe setzen.
 *
 * Rot-Probe: `field-sizing-content` aus `components/ui/textarea.tsx`
 * entfernt → `native` rot; `useAutoGrow` auf No-op → `fallback` rot.
 */
// ~300 Zeichen: passt bei 320 x 568 (60 svh = 340 px) sicher unter die Grenze.
const MID_TEXT =
  'Ist der Kalender-Server nicht erreichbar, nennt der Agent die offenen Termine aus dem ' +
  'letzten Protokoll und bittet darum, den Termin von Hand einzutragen. Er schlaegt keine ' +
  'Uhrzeiten vor, die er nicht pruefen kann, und weist darauf hin, dass Einladungen erst ' +
  'nach der Wiederherstellung verschickt werden.'

for (const mode of ['native', 'fallback'] as const) {
  test(`M5 (${mode}): Textfeld waechst mit, kein innerer Scroll unter 60 svh, Fokus bleibt`, async ({
    page,
    request,
  }) => {
    test.setTimeout(90_000)
    if (mode === 'fallback') {
      await page.addInitScript(() => {
        const original = CSS.supports.bind(CSS)
        CSS.supports = ((...args: [string, string?]) =>
          String(args[0]).includes('field-sizing')
            ? false
            : original(...(args as [string, string]))) as typeof CSS.supports
        document.addEventListener('DOMContentLoaded', () => {
          const style = document.createElement('style')
          style.textContent = 'textarea{field-sizing:fixed!important}'
          document.head.appendChild(style)
        })
      })
    }

    const user = await createUser(request)
    await loginAs(page, user)
    await decideCookieConsent(page)
    const { workspaceId } = await seedWorkspace(request, user)
    const token = user.session.access_token
    const tool = await apiRequest<{ id: string }>(
      request,
      token,
      `/v1/workspaces/${workspaceId}/external_tools`,
      {
        method: 'POST',
        data: { name: 'E2E Autogrow Tool', content: { display_name: 'Autogrow', fallback_note: MID_TEXT } },
      },
    )

    await page.goto(`/w/${workspaceId}/tools/${tool.id}`)
    const field = page.getByLabel('Fallback-Hinweis', { exact: false }).or(
      page.getByLabel('Fallback note', { exact: false }),
    )
    await expect(field.first()).toHaveValue(MID_TEXT)
    const textarea = field.first()

    const probe = () =>
      textarea.evaluate((el: HTMLTextAreaElement) => ({
        client: el.clientHeight,
        scroll: el.scrollHeight,
        cap: window.innerHeight * 0.6,
        supports: CSS.supports('field-sizing', 'content'),
        inlineHeight: el.style.height,
        focused: document.activeElement === el,
      }))

    const loaded = await probe()
    // Sicherstellen, dass der gewuenschte Pfad wirklich aktiv ist — sonst
    // misst der Test zweimal dasselbe.
    expect(loaded.supports).toBe(mode === 'native')
    if (mode === 'native') expect(loaded.inlineHeight).toBe('')
    else expect(loaded.inlineHeight).not.toBe('')
    expect(loaded.scroll, 'Seed-Text muss unter 60 svh liegen').toBeLessThanOrEqual(loaded.cap)
    expect(loaded.scroll, 'innerer Scroll trotz Inhalt < 60 svh').toBeLessThanOrEqual(
      loaded.client + 1,
    )

    // Tippen: das Feld waechst Zeile um Zeile, der Fokus bleibt im Feld.
    await textarea.click()
    await textarea.press('Control+End')
    const before = loaded.client
    await textarea.pressSequentially(' Zweiter Absatz folgt.\nNoch eine Zeile.\nUnd eine dritte.')
    const typed = await probe()
    expect(typed.focused, 'Fokus hat das Feld beim Wachsen verlassen').toBe(true)
    expect(typed.client).toBeGreaterThan(before)
    expect(typed.scroll).toBeLessThanOrEqual(typed.client + 1)

    // Obergrenze: weit ueber 60 svh scrollt das Feld innen, die Hoehe bleibt gedeckelt.
    await textarea.fill(`${MID_TEXT}\n`.repeat(12))
    const capped = await probe()
    expect(capped.client).toBeLessThanOrEqual(Math.ceil(capped.cap) + 1)
    expect(capped.scroll).toBeGreaterThan(capped.client)
  })
}

/**
 * Mobil-Spec M11: Tabellen-Muster am Beispiel der Arbeitsbereich-Tabelle
 * (8 Spalten, 988 px breit). Vorher bei 320 px: Scroll-Bereich 238 von
 * 988 px, nicht fokussierbar, ohne Namen, erste Spalte scrollte mit weg,
 * kein Hinweis.
 *
 * Geprueft auf jedem Profil, solange die Tabelle ueberlaeuft: der Bereich ist
 * ein Tab-Stopp mit Namen (ACT 0ssw9k), `overscroll-behavior-x: contain`,
 * die erste Spalte bleibt nach dem Scrollen am linken Rand, und der Hinweis
 * erscheint genau unter `md`. Dazu das Navigations-Sheet: `overscroll-
 * behavior: contain` (kein Scroll-Chaining in die Seite dahinter).
 *
 * Rot-Proben: `tabIndex` im Wrapper von `components/ui/table.tsx` entfernt →
 * rot; `sticky` der ersten Spalte entfernt → rot (Spalte bei -120 px);
 * `overscroll-contain` am Sheet in `AppShell.tsx` entfernt → rot unter `md`.
 */
test('M11: breite Tabelle ist fokussierbar, benannt, erste Spalte fixiert, Hinweis unter md', async ({
  page,
  request,
}) => {
  test.setTimeout(60_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const post = <T>(path: string, data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method: 'POST', data })

  const area = await post<{ id: string }>('/work-areas', { name: 'E2E Tabellen-Area' })
  const columns = ['kunde', 'region', 'produkt', 'status', 'kommentar'].map((name) => ({
    name,
    type: 'text',
  }))
  const table = await post<{ id: string }>(`/work-areas/${area.id}/tables`, {
    name: 'auftraege',
    schema: {
      columns: [
        { name: 'occurred_at', type: 'date', nullable: false },
        ...columns,
        { name: 'menge', type: 'integer' },
        { name: 'umsatz', type: 'numeric' },
      ],
    },
  })
  await post(`/wa-tables/${table.id}/rows`, {
    rows: Array.from({ length: 5 }, (_, i) => ({
      occurred_at: `2026-09-0${i + 1}`,
      kunde: `Kunde ${i + 1} GmbH`,
      region: 'Nord',
      produkt: 'Lizenzpaket Team',
      status: 'offen',
      kommentar: 'Rueckfrage zum Liefertermin',
      menge: i + 1,
      umsatz: (i + 1) * 99.9,
    })),
  })

  const viewport = page.viewportSize()?.width ?? 0
  const isPhone = viewport < 768
  await page.goto(`/w/${workspaceId}/workarea/areas/${area.id}/tables/${table.id}`)
  await expect(page.getByText('Kunde 1 GmbH')).toBeVisible()
  await expectNoHorizontalScroll(page, 'workarea/tables/:id')

  const preview = page.getByRole('table', { name: /^(Daten|Data)$/ })
  const scroller = page.getByTestId('table-scroller').filter({ has: preview })
  const overflowing = await scroller.evaluate((el) => el.scrollWidth > el.clientWidth + 1)
  // Auf dem Desktop passt die Tabelle — dann gilt das Muster nicht, und es
  // darf auch keinen zusaetzlichen Tab-Stopp geben.
  if (!overflowing) {
    await expect(scroller).not.toHaveAttribute('tabindex')
    return
  }

  await expect(scroller).toHaveAttribute('tabindex', '0')
  await expect(page.getByRole('region', { name: /^(Daten|Data)$/ })).toBeVisible()
  expect(await scroller.evaluate((el) => getComputedStyle(el).overscrollBehaviorX)).toBe('contain')

  const hint = page.getByText(/Seitlich wischen für weitere Spalten|Swipe sideways for more columns/)
  if (isPhone) await expect(hint.first()).toBeVisible()
  else await expect(hint.first()).toBeHidden()

  // Mit dem Fokus auf dem Bereich scrollen die Pfeiltasten (ACT 0ssw9k).
  await scroller.focus()
  await expect(scroller).toBeFocused()
  await page.keyboard.press('ArrowRight')
  await expect.poll(() => scroller.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0)

  // Nach dem Scrollen liegt die erste Spalte weiter am linken Rand.
  await scroller.evaluate((el) => {
    el.scrollLeft = 120
  })
  const offset = await scroller.evaluate((el) => {
    const cell = el.querySelector('tbody tr > :first-child') as HTMLElement
    return {
      scrollLeft: el.scrollLeft,
      left: Math.round(cell.getBoundingClientRect().left - el.getBoundingClientRect().left),
    }
  })
  expect(offset.scrollLeft).toBeGreaterThan(0)
  expect(offset.left, 'erste Spalte ist mitgescrollt statt fixiert').toBe(0)

  // Navigations-Sheet (nur unter md sichtbar): kein Scroll-Chaining.
  if (isPhone) {
    await page.getByTestId('app-nav-open').click()
    const sheet = page.getByRole('dialog')
    await expect(sheet).toBeVisible()
    expect(await sheet.evaluate((el) => getComputedStyle(el).overscrollBehaviorY)).toBe('contain')
  }
})

/**
 * Mobil-Spec P7, M10: Im Artefakt-Detail lag die Textspalte bei 320 px neben
 * dem Anker-Knopf und war 170 px breit. Unter md nutzt der Text die volle
 * Blockbreite; der Knopf sitzt oben rechts im Block, der Text fliesst um ihn.
 *
 * Rot-Probe: gegen das Image von origin/main rot (Textspalte schmaler als der
 * Block).
 */
test('M10: Artefakt-Text unter md in voller Blockbreite', async ({ page, request }) => {
  test.setTimeout(60_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const call = <T>(path: string, data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method: 'POST', data })

  const area = await call<{ id: string }>('/work-areas', { name: 'E2E Artefakt-Area' })
  const artifact = await call<{ id: string }>(`/work-areas/${area.id}/artifacts`, {
    title: 'E2E Protokoll',
    content_md: Array.from(
      { length: 4 },
      (_, i) => `Absatz ${i + 1}: Im Quartalsgespräch wurde die neue Preisliste vereinbart.`,
    ).join('\n\n'),
    occurred_at: '2026-09-29T10:00:00Z',
  })

  const isPhone = (page.viewportSize()?.width ?? 0) < 768
  await page.goto(`/w/${workspaceId}/workarea/areas/${area.id}/artifacts/${artifact.id}`)
  const text = page.locator('main ol pre').first()
  await expect(text).toBeVisible()
  await expectNoHorizontalScroll(page, 'workarea/artifacts/:id')
  const widths = await text.evaluate((el) => ({
    text: el.getBoundingClientRect().width,
    block: (el.parentElement as HTMLElement).clientWidth,
  }))
  if (isPhone) {
    // `li` hat 2 × 8 px Polsterung; der Text fuellt den Rest ganz.
    expect(widths.text, 'Artefakt-Text unter md nicht in voller Breite').toBeGreaterThanOrEqual(
      widths.block - 16 - 1,
    )
  }
})

/**
 * Mobil-Spec W4=b (R-P3): „Feedback geben“ und „Problem melden“ oeffnen
 * unterhalb `md` eine eigene Vollbildseite statt eines Dialogs; ab `md`
 * bleibt der Dialog. Geprueft auf jedem Profil, scharf auf `mobile-320`:
 * oeffnen, ausfuellen, absenden, zurueck — mit erhaltenem `?tab=` der
 * Ausgangsseite, Browser-Zurueck und ohne horizontalen Seiten-Scroll.
 *
 * Rot-Probe: Mobil-Weiche in `GiveFeedbackDialog`/`ReportProblemDialog`
 * abgeschaltet (`isMobile && false`) → Phone-Zweig rot (kein Link).
 */
test('W4=b: Feedback geben/Problem melden unter md als eigene Seite, ab md Dialog', async ({
  page,
  request,
}) => {
  test.setTimeout(90_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const resource = await apiRequest<{ id: string }>(
    request,
    token,
    `/v1/workspaces/${workspaceId}/resources`,
    {
      method: 'POST',
      data: {
        name: 'E2E Feedback Resource',
        content: { description: 'Kurz.', blocks: blockDoc('Inhalt').blocks },
      },
    },
  )
  const ws = `/w/${workspaceId}`
  const origin = `${ws}/resources/${resource.id}?tab=versions`
  const isPhone = (page.viewportSize()?.width ?? 0) < 768
  // Sprachneutral: Deutsch oder Englisch, je nach Browser-Locale des Profils.
  const giveName = /Feedback geben|Give feedback/
  const reportName = /Problem melden|Report a problem/

  await page.goto(origin)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  if (!isPhone) {
    // Ab `md`: Dialog, die Route bleibt stehen.
    await page.getByRole('button', { name: giveName }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    expect(new URL(page.url()).pathname).toBe(`${ws}/resources/${resource.id}`)
    return
  }

  // Audit A13: unter md liegt „Feedback geben“ im Seitenkopf hinter „Mehr“
  // (`DetailHeader.collapseActionsBelowMd`). Eingeklappt ist der Link
  // `hidden` und damit nicht im A11y-Tree; erst aufklappen, dann klicken.
  // Nach jeder Navigation ist der Kopf wieder eingeklappt.
  const openGiveFeedback = async () => {
    const more = page.getByTestId('detail-header-more')
    await expect(more).toHaveAttribute('aria-expanded', 'false')
    await expect(page.getByRole('link', { name: giveName })).toHaveCount(0)
    await more.click()
    await expect(more).toHaveAttribute('aria-expanded', 'true')
    await page.getByRole('link', { name: giveName }).click()
  }

  // --- Feedback geben: oeffnen, ausfuellen, absenden, zurueck mit Bestaetigung.
  await openGiveFeedback()
  await expect(page).toHaveURL(new RegExp(`/feedback/give/resource/${resource.id}`))
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(giveName)
  await expectNoHorizontalScroll(page, 'feedback/give (Vollbild)')
  await page.locator('select').first().selectOption('outdated')
  await page.locator('textarea').first().fill(`${MID_TEXT}\n`.repeat(3))
  await expectNoHorizontalScroll(page, 'feedback/give (ausgefuellt)')
  await page.getByRole('button', { name: /^(Absenden|Submit)$/ }).click()
  await expect(page).toHaveURL((url) => `${url.pathname}${url.search}` === origin)
  await expect(page.getByText(/Danke für dein Feedback|Thanks for your feedback/)).toBeVisible()

  // Das Feedback liegt wirklich am Element (Element-ID ueber die Route erhalten).
  const items = await apiRequest<{ items: Array<{ entity_id: string; signal: string }> }>(
    request,
    token,
    `/v1/workspaces/${workspaceId}/feedback-items`,
  )
  expect(items.items.some((i) => i.entity_id === resource.id && i.signal === 'outdated')).toBe(
    true,
  )

  // --- Browser-Zurueck: Seite oeffnen, Browser-Zurueck fuehrt zur Ausgangsseite.
  await openGiveFeedback()
  await expect(page).toHaveURL(/\/feedback\/give\//)
  await page.goBack()
  await expect(page).toHaveURL((url) => `${url.pathname}${url.search}` === origin)

  // --- Problem melden (Feedback-Uebersicht): oeffnen, ausfuellen, absenden, zurueck.
  await page.goto(`${ws}/feedback`)
  await page.getByRole('link', { name: reportName }).click()
  await expect(page).toHaveURL(new RegExp(`${ws}/feedback/report$`))
  await expectNoHorizontalScroll(page, 'feedback/report (Vollbild)')
  await page.locator('textarea').first().fill('Tool antwortet nicht.')
  await page.getByRole('button', { name: /^(Melden|Report)$/ }).click()
  await expect(page).toHaveURL(new RegExp(`${ws}/feedback$`))
  await expect(page.getByText(/Problem gemeldet|Problem reported/)).toBeVisible()
})

/**
 * Mobil-Spec M7 (Owner-Weiche W1=a): Tab-Leisten brechen um, statt
 * horizontal zu scrollen. Vorher lagen bei 320 px im Agent-Detail
 * „Werkzeuge & Rechte“ und „Verbindung“ (Leiste 461 von 288 px) und im
 * Resource-Detail „Verwendung“ und „Versionen“ (540 von 288 px) ausserhalb
 * der Leiste — auch bei 390 und 430 px blieb je mindestens ein Tab verdeckt.
 *
 * Geprueft auf jedem Profil: keine `tablist` mit eigener Scrollweite, jeder
 * Tab liegt ganz im Viewport und ist mindestens 44 px hoch, die Leiste traegt
 * ihren Namen, und der Deep-Link `?tab=versions` waehlt weiterhin den
 * Versions-Tab und bleibt in der URL.
 *
 * Rot-Proben: `flex-wrap` in `components/ui/tabs.tsx` wieder durch
 * `overflow-x-auto` ersetzt → rot auf `mobile-320` und `mobile-iphone-13`
 * (Agent und Resource); `aria-label` der Resource-Leiste zurueck auf
 * `detail.subResourcesTitle` → rot auf jedem Profil.
 */
test('M7: Tab-Leisten brechen um, jeder Tab liegt im Viewport, ?tab= bleibt', async ({
  page,
  request,
}) => {
  test.setTimeout(90_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const post = <T>(path: string, data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method: 'POST', data })

  const agent = await post<{ id: string }>('/agents', { name: 'E2E Tabs Agent' })
  const resource = await post<{ id: string }>('/resources', {
    name: 'E2E Tabs Resource',
    content: { description: 'Kurz.', blocks: blockDoc('Inhalt').blocks },
  })
  const persona = await post<{ id: string }>('/personas', {
    name: 'E2E Tabs Persona',
    content: { description: 'Kurz.', tags: [], content: blockDoc('Profil') },
  })

  const ws = `/w/${workspaceId}`
  // Dritter Wert: Tab-Anzahl; vierter: erwarteter Name der Leiste. Persona
  // und Resource tragen den gemeinsamen Namen „Detailansicht“ (vorher:
  // Persona ohne Namen, Resource faelschlich „Sub-Resources“).
  const detailView = /^(Detailansicht|Detail view)$/
  // Agent: Seiten-Leiste (Navigation §3.1) und, im Tab „Einstellungen“, die
  // innere Leiste des Editors (fuenfter Wert: Index der Leiste) — die war die
  // Ausloeserin von M7 (461 von 288 px).
  const routes: Array<[string, string, number, RegExp, number?]> = [
    [`${ws}/agents/${agent.id}`, 'agents/:id', 4, /^(Bereiche des Agenten|Agent sections)$/],
    [`${ws}/agents/${agent.id}?tab=settings`, 'agents/:id?tab=settings', 3, /.+/, 1],
    [`${ws}/resources/${resource.id}`, 'resources/:id', 4, detailView],
    [`${ws}/personas/${persona.id}`, 'personas/:id', 5, detailView],
  ]

  const failures: string[] = []
  for (const [path, label, tabCount, expectedName, index = 0] of routes) {
    await page.goto(path)
    const tablist = page.getByRole('tablist').nth(index)
    await expect(tablist.getByRole('tab')).toHaveCount(tabCount)
    const probe = await tablist.evaluate((list) => {
      const viewport = document.documentElement.clientWidth
      const tabs = Array.from(list.querySelectorAll<HTMLElement>('[role="tab"]'))
      return {
        name: list.getAttribute('aria-label'),
        scrollWidth: list.scrollWidth,
        clientWidth: list.clientWidth,
        outside: tabs
          .filter((tab) => {
            const rect = tab.getBoundingClientRect()
            return rect.left < 0 || rect.right > viewport + 1
          })
          .map((tab) => tab.textContent?.trim() ?? '?'),
        minHeight: Math.min(...tabs.map((tab) => tab.getBoundingClientRect().height)),
      }
    })
    if (probe.scrollWidth > probe.clientWidth + 1) {
      failures.push(`${label}: tablist scrollt (${probe.scrollWidth} > ${probe.clientWidth})`)
    }
    if (probe.outside.length > 0) {
      failures.push(`${label}: Tabs ausserhalb des Viewports: ${probe.outside.join(', ')}`)
    }
    if (probe.minHeight < 44) {
      failures.push(`${label}: Tab nur ${probe.minHeight}px hoch (< 44)`)
    }
    if (!expectedName.test(probe.name ?? '')) {
      failures.push(`${label}: tablist-Name „${probe.name ?? ''}“ passt nicht zu ${expectedName}`)
    }
  }
  expect(failures, 'Tab-Leisten mit verdeckten oder zu kleinen Tabs').toEqual([])

  // Deep-Link unveraendert: `?tab=versions` waehlt den Versions-Tab.
  await page.goto(`${ws}/resources/${resource.id}?tab=versions`)
  await expect(page.getByRole('tab', { selected: true })).toHaveText(/Versionen|Versions/)
  expect(new URL(page.url()).searchParams.get('tab')).toBe('versions')
})

/**
 * Mobil-Spec M2 + Navigation-Spec §3.1: Die Agent-Seite hat Tabs; die Karte
 * „Zusammensetzung“ steht im Tab „Überblick“ hinter der Tab-Leiste. Die
 * Klapp-Regel aus t_42bff43b (Karte unter md zugeklappt) ist deshalb
 * entfallen. Vor den Tabs lag die Oberkante der Tab-Leiste bei 320 × 568 auf
 * 1,80 Bildschirmen (Agent mit Persona, System-Prompt und 14 Playbooks).
 *
 * Geprueft auf jedem Profil: kein Schalter, Karte offen, Persona-Link
 * sichtbar; die Tab-Leiste der Seite steht im Dokument vor der Karte. Unter
 * md zusaetzlich: Tab-Oberkante <= 1,2 Bildschirme bei 320 px Breite und
 * <= 0,9 auf den breiteren Phones (dieselben Grenzen wie zuvor mit
 * zugeklappter Karte); vier Playbooks und „8 weitere anzeigen“ (P7); kein
 * Seitwaerts-Scroll.
 *
 * Rot-Probe: `<AgentHierarchyView>` in `AgentDetailPage.tsx` vor die
 * `<Tabs>` ziehen → rot auf `mobile-320` und `mobile-iphone-13` (Oberkante
 * und Reihenfolge).
 */
test('M2: Agent-Detail unter md mit Tab-Leiste vor der offenen Zusammensetzung', async ({
  page,
  request,
}) => {
  test.setTimeout(120_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const call = <T>(path: string, method: 'POST' | 'PUT', data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method, data })

  const description = 'Begleitet neue Teammitglieder durch die ersten Wochen und fasst Rückfragen zusammen.'
  const persona = await call<{ id: string }>('/personas', 'POST', {
    name: 'E2E Onboarding-Begleitung',
    content: { description, tags: [], content: blockDoc('Profil') },
  })
  const systemPrompt = await call<{ id: string }>('/system-prompts', 'POST', {
    name: 'E2E Kundenservice-Grundprompt',
    content: { description, body: JSON.stringify(blockDoc('Du bist {{ persona.name }}').blocks) },
  })
  const playbookIds: string[] = []
  for (let i = 1; i <= 14; i++) {
    const playbook = await call<{ id: string }>('/playbooks', 'POST', {
      name: `E2E Zusammensetzung Playbook ${i}`,
      content: { description: 'Kurz.' },
    })
    playbookIds.push(playbook.id)
  }
  await call(`/personas/${persona.id}/playbooks`, 'PUT', { playbook_ids: playbookIds })
  const agent = await call<{ id: string }>('/agents', 'POST', {
    name: 'E2E Vertriebs-Assistent',
    description,
    persona_id: persona.id,
    system_prompt_template_id: systemPrompt.id,
  })

  await page.goto(`/w/${workspaceId}/agents/${agent.id}`)
  const card = page.getByTestId('agent-hierarchy')
  await expect(card).toBeVisible()
  const viewport = page.viewportSize()!
  const tabs = page.getByRole('tablist', { name: /^(Bereiche des Agenten|Agent sections)$/ })
  await expect(tabs).toBeVisible()
  await expect(page.getByRole('tab', { selected: true })).toHaveText(/Überblick|Overview/)

  // Auf jeder Breite: kein Schalter, Inhalt offen, Links direkt erreichbar.
  await expect(card.getByTestId('agent-hierarchy-toggle')).toHaveCount(0)
  await expect(card.getByRole('button', { name: /^(Zusammensetzung|Composition)/ })).toHaveCount(0)
  await expect(card.locator('[aria-expanded], [hidden]')).toHaveCount(0)
  await expect(card.getByRole('link', { name: 'E2E Onboarding-Begleitung' })).toBeVisible()
  await expect(card.getByRole('link', { name: 'E2E Kundenservice-Grundprompt' })).toBeVisible()

  const probe = await tabs.evaluate((list) => {
    const hierarchy = document.querySelector('[data-testid="agent-hierarchy"]')!
    return {
      screens: (list.getBoundingClientRect().top + window.scrollY) / window.innerHeight,
      // Die Karte folgt der Tab-Leiste im Dokument (steht im Tab „Überblick“).
      tabsBeforeCard: Boolean(
        list.compareDocumentPosition(hierarchy) & Node.DOCUMENT_POSITION_FOLLOWING,
      ),
    }
  })
  expect(probe.tabsBeforeCard, 'Tab-Leiste steht vor der Zusammensetzung').toBe(true)

  if (viewport.width >= 768) {
    await expect(card.getByTestId('agent-hierarchy-playbook')).toHaveCount(14)
    return
  }

  const limit = viewport.width <= 320 ? 1.2 : 0.9
  expect(probe.screens, `Tab-Oberkante in Bildschirmen bei ${viewport.width} px`).toBeLessThanOrEqual(
    limit,
  )

  await expect(card.getByTestId('agent-hierarchy-playbook')).toHaveCount(4)
  await expect(card.getByRole('button', { name: /^(8 weitere anzeigen|Show 8 more)$/ })).toBeVisible()
  await expectNoHorizontalScroll(page, 'agents/:id (Überblick, Zusammensetzung offen)')
})

/**
 * Mobil-Spec M4 (Owner-Weiche W2=a): Der Text-Diff im Versionen-Tab bricht
 * auf jeder Breite um, statt seitlich zu scrollen. Vorher war der Wrapper
 * `overflow-x-auto` mit `scrollWidth` 12.919 px bei 210 px (320) bzw.
 * 280 px (390). Eine 1.100-Zeichen-Beschreibung lag als eine einzige Zeile da.
 *
 * Geprueft auf jedem Profil, Desktop eingeschlossen (W2=a, keine
 * Doppeldarstellung): Im Diff hat kein Element `scrollWidth > clientWidth`.
 * Ausgenommen sind die `sr-only`-Praefixe (1 px, nicht sichtbar). Jede Zeile
 * hat die feste Rinne links, die Folgezeilen beginnen rechts davon. Die Seite
 * scrollt nicht horizontal.
 *
 * Rot-Probe: `overflow-x-auto` + `min-w-max` + `whitespace-pre` in
 * `VersionDiffView.tsx` zurueck → rot auf jedem Profil.
 */
test('M4: Versions-Diff bricht um, kein Seitwaerts-Scroller (W2=a)', async ({ page, request }) => {
  test.setTimeout(60_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const call = <T>(path: string, method: 'POST' | 'PUT', data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method, data })

  // v1 aktiv, v2 als Entwurf mit langer Beschreibung samt URL ohne
  // Trennstelle. Das Persona-Profil beginnt mit der Beschreibung, also steht
  // sie im Text-Diff.
  const sentence = 'Moderiert Feedbackgespräche zwischen Teammitgliedern und hält Vereinbarungen fest. '
  const longDescription = `${sentence.repeat(12)}Leitfaden: ${LONG_URL}`
  const persona = await call<{ id: string }>('/personas', 'POST', {
    name: 'E2E Diff Persona',
    content: { description: 'Kurz.', tags: [], content: blockDoc('Profil') },
  })
  for (const to of ['review', 'active']) {
    await call(`/personas/${persona.id}/versions/1/transition`, 'POST', { to })
  }
  await call(`/personas/${persona.id}`, 'PUT', {
    name: 'E2E Diff Persona',
    content: { description: longDescription, tags: [], content: blockDoc('Profil') },
  })

  await page.goto(`/w/${workspaceId}/personas/${persona.id}?tab=versions&diff=2`)
  const diff = page.getByRole('list', { name: /^(Inhalts-Diff|Content diff)$/ })
  await expect(diff).toBeVisible()
  // Der Verursacher muss gerendert sein, sonst misst die Probe blind gruen.
  await expect(diff.getByText(LONG_URL, { exact: false })).toBeVisible()
  await expectNoHorizontalScroll(page, 'personas/:id?tab=versions (Diff offen)')

  const probe = await diff.evaluate((list) => {
    const wrapper = list.parentElement as HTMLElement
    const scrollers = [wrapper, ...Array.from(list.querySelectorAll<HTMLElement>('*'))]
      .filter((el) => !el.classList.contains('sr-only'))
      .filter((el) => el.scrollWidth > el.clientWidth + 1)
      .map((el) => `${el.tagName.toLowerCase()}.${el.className} ${el.scrollWidth}/${el.clientWidth}`)
    const line = list.querySelector<HTMLElement>('li[data-kind="added"]')!
    const [gutter, text] = Array.from(line.children) as HTMLElement[]
    const gutterBox = gutter.getBoundingClientRect()
    const textBox = text.getBoundingClientRect()
    return {
      scrollers,
      gutterWidth: Math.round(gutterBox.width),
      textOffset: Math.round(textBox.left - gutterBox.left),
      textLines: Math.round(textBox.height / parseFloat(getComputedStyle(text).lineHeight)),
    }
  })
  expect(probe.scrollers, 'Elemente im Diff mit eigener Scrollweite').toEqual([])
  // Rinne 1,25 rem = 20 px; der Text (und damit jede Folgezeile) beginnt
  // rechts davon, nicht unter dem Zeichen.
  expect(probe.gutterWidth).toBe(20)
  expect(probe.textOffset).toBeGreaterThanOrEqual(20)
  // Die lange Zeile ist wirklich umbrochen (vorher: genau eine Zeile).
  expect(probe.textLines).toBeGreaterThan(1)
})

test('M9/M11: Mitglieder als Liste, Auswahllisten ohne Scroll-in-Scroll unter md', async ({
  page,
  request,
}) => {
  test.setTimeout(120_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`
  const post = <T>(path: string, data: unknown) =>
    apiRequest<T>(request, token, `${base}${path}`, { method: 'POST', data })

  // Zwoelf Kandidaten je Liste: mehr als die 8er-Schrittweite, damit unter md
  // der „weitere anzeigen“-Knopf entsteht.
  const persona = await post<{ id: string }>('/personas', {
    name: 'E2E Auswahl Persona',
    content: { description: 'Kurz.', tags: [], content: blockDoc('Profil') },
  })
  const resource = await post<{ id: string }>('/resources', {
    name: 'E2E Auswahl Resource',
    content: { description: 'Kurz.', blocks: blockDoc('Inhalt').blocks },
  })
  for (let i = 1; i <= 12; i++) {
    await post('/playbooks', { name: `E2E Auswahl Playbook ${i}`, content: { description: 'Kurz.' } })
    await post('/resources', {
      name: `E2E Auswahl Kandidat ${i} ${LONG_URL}`,
      content: { description: 'Kurz.', blocks: blockDoc('Inhalt').blocks },
    })
  }

  const ws = `/w/${workspaceId}`
  const mobile = page.viewportSize()!.width < 768

  // Mitglieder: unter md Liste ohne Tabelle, ab md die Tabelle.
  await page.goto(`${ws}/settings/members`)
  if (mobile) {
    await expect(page.getByTestId('members-list').getByRole('listitem')).toHaveCount(1)
    await expect(page.getByRole('table')).toHaveCount(0)
    await page.getByRole('button', { name: /Mehr anzeigen|Show more/ }).click()
    await expect(page.getByRole('button', { name: /Entfernen|Remove/ })).toBeVisible()
  } else {
    await expect(page.getByRole('table')).toHaveCount(1)
  }
  await expectNoHorizontalScroll(page)

  // Beide Auswahllisten: dasselbe Muster, je nach Breite.
  const pickers: Array<[string, string, () => Promise<void>]> = [
    [
      `${ws}/personas/${persona.id}?tab=playbooks`,
      'persona-playbooks-available',
      () => page.getByRole('button', { name: /Verknüpfungen bearbeiten|Edit links/ }).click(),
    ],
    [`${ws}/resources/${resource.id}?tab=sub`, 'sub-resource-available', async () => {}],
  ]
  for (const [path, testId, open] of pickers) {
    await page.goto(path)
    await open()
    const frame = page.getByTestId(testId)
    const list = frame.getByRole('list')
    await expect(list).toBeVisible()
    const style = await frame.evaluate((el) => {
      const cs = getComputedStyle(el)
      return { maxHeight: cs.maxHeight, overflowY: cs.overflowY, tab: el.getAttribute('tabindex') }
    })
    if (mobile) {
      expect(style, `${testId}: kein innerer Scroller unter md`).toEqual({
        maxHeight: 'none',
        overflowY: 'visible',
        tab: null,
      })
      // Der Seed-Workspace bringt eigene Eintraege mit; die Gesamtzahl steht
      // deshalb nicht fest — der Knopf nennt, wie viele er nachlaedt.
      await expect(list.getByRole('listitem')).toHaveCount(8)
      const more = page.getByRole('button', { name: /weitere anzeigen|more/ })
      const step = Number((await more.textContent())?.match(/\d+/)?.[0])
      expect(step).toBeGreaterThan(0)
      await more.click()
      await expect(list.getByRole('listitem')).toHaveCount(8 + step)
      // Fokus liegt im ersten neuen Eintrag, nicht auf body.
      expect(
        await list.getByRole('listitem').nth(8).evaluate((li) => li.contains(document.activeElement)),
      ).toBe(true)
    } else {
      expect(style.overflowY).toBe('auto')
      expect(style.tab).toBe('0')
      await expect.poll(() => list.getByRole('listitem').count()).toBeGreaterThanOrEqual(12)
      await expect(page.getByRole('button', { name: /weitere anzeigen|Show \d+ more/ })).toHaveCount(0)
    }
    await expectNoHorizontalScroll(page)
  }
})

/**
 * Gedaechtnis-Spec §5 / C5a (t_10a996a6): Die Warteschlange „Zur Freigabe“
 * rendert auf jeder Breite ohne horizontalen Seiten-Scroll — mit den
 * breitesten Bausteinen der Seite gleichzeitig: Zurueckgehaltene mit langem
 * Fakt (URL ohne Trennstelle), Gruppenkopf mit langem Agentennamen und
 * „Alle … freigeben“, Aenderungsvorschlag mit Wort-Diff, offene Stapelleiste
 * (fixed bottom) und der Bestaetigungsdialog der Gruppenfreigabe.
 *
 * Der Agent ist echt (Seed ueber die API), die Gedaechtnis-Endpunkte werden
 * per `page.route` bedient: die Eintraege liefen sonst ueber den Agentenpfad
 * mit MCP-Token und Policy, und gemessen werden soll hier das Layout, nicht
 * die Schreibkette (die decken die API-Tests ab).
 *
 * Rot-Probe: `whitespace-normal` am Gruppen-Freigabeknopf in
 * `ApprovalQueue.tsx` entfernt (Button-Basis `whitespace-nowrap`) → rot auf
 * `mobile-320` und `mobile-iphone-13` (gemessen 425 > 390 px).
 */
test('C5a: /memory „Zur Freigabe“ ohne Seiten-Scroll – Gruppen, Vorschlag, Stapelleiste, Dialog', async ({
  page,
  request,
}) => {
  test.setTimeout(60_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const me = await apiRequest<{ user_id: string }>(request, token, '/v1/me')
  const agentName = 'E2E Vertriebsassistenz für Bestandskunden Nord und Süd'
  const agent = await apiRequest<{ id: string }>(
    request,
    token,
    `/v1/workspaces/${workspaceId}/agents`,
    { method: 'POST', data: { name: agentName } },
  )

  const now = '2026-10-03T08:00:00Z'
  const row = (id: string, fact: string, extra: Record<string, unknown> = {}) => ({
    id,
    agent_id: agent.id,
    status: 'pending',
    fact,
    context: 'Aus dem Gespräch vom Vormittag.',
    category: 'fact',
    importance: 3,
    source: 'agent',
    triage_note: null,
    retrieval_count: 0,
    last_retrieved_at: null,
    created_at: now,
    updated_at: now,
    kind: 'agent_note',
    scope: 'agent',
    subject_user_id: null,
    origin: 'user_stated',
    created_by_agent_id: agent.id,
    occurrence_count: 1,
    ...extra,
  })
  const held = [
    row('e2e-held-1', `Laut Wiki gilt die Preisliste ${LONG_URL} ab sofort für alle Kunden.`, {
      origin: 'external_content',
    }),
    row('e2e-held-2', 'Antworte Kunden aus Österreich immer mit Sie.', { category: 'instruction' }),
  ]
  const items = [
    row('e2e-mine-1', 'Ich bevorzuge kurze Zusammenfassungen am Ende.', {
      agent_id: null,
      scope: 'user',
      kind: 'user_fact',
      subject_user_id: me.user_id,
    }),
    row('e2e-note-1', 'Bestandskunden Nord bestellen meist im ersten Quartal.'),
    row('e2e-note-2', 'Rückfragen zu Lieferterminen gehen an die Logistik.'),
    row('e2e-note-3', 'Rabattstaffeln stehen im CRM unter Konditionen.'),
  ]
  const target = row('e2e-target-1', 'Der Ansprechpartner bei Kunde Nord ist Frau Schmidt.', {
    status: 'active',
  })
  const proposals = [
    {
      id: 'e2e-proposal-1',
      memory_id: target.id,
      agent_id: agent.id,
      action: 'change',
      new_fact: 'Der Ansprechpartner bei Kunde Nord ist seit Oktober Herr Yilmaz.',
      reason: 'Wechsel im Einkauf laut Mail vom 2. Oktober.',
      status: 'pending',
      decided_by: null,
      decided_at: null,
      created_at: now,
    },
  ]
  const json = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
  await page.route(/\/v1\/workspaces\/[^/]+\/memories\/counts(\?|$)/, (route) => {
    const params = new URL(route.request().url()).searchParams
    if (params.get('held') === 'true') return route.fulfill(json({ total: held.length }))
    if (params.get('scope') === 'user') return route.fulfill(json({ total: 1 }))
    return route.fulfill(json({ total: 3, groups: { agent: { [agent.id]: 3 } } }))
  })
  await page.route(/\/v1\/workspaces\/[^/]+\/memories(\?|$)/, (route) => {
    const params = new URL(route.request().url()).searchParams
    const rows = params.get('held') === 'true' ? held : items
    return route.fulfill(json({ items: rows, next_cursor: null }))
  })
  await page.route(/\/v1\/workspaces\/[^/]+\/memory-proposals(\?|$)/, (route) =>
    route.fulfill(json(proposals)),
  )
  await page.route(/\/v1\/workspaces\/[^/]+\/me\/memories(\?|$)/, (route) =>
    route.fulfill(json({ items: [items[0]], next_cursor: null })),
  )
  await page.route(/\/v1\/workspaces\/[^/]+\/agents\/[^/]+\/memories(\?|$)/, (route) =>
    route.fulfill(json([target])),
  )

  await page.goto(`/w/${workspaceId}/memory`)
  await expect(page).toHaveURL(/[?&]tab=approval/)
  await expect(page.getByTestId('memory-held-row')).toHaveCount(2)
  await expect(page.getByTestId('memory-proposal-row')).toBeVisible()
  await expect(page.getByRole('heading', { level: 3, name: new RegExp(agentName) })).toBeVisible()
  // Der Verursacher muss gerendert sein, sonst misst die Probe blind gruen.
  await expect(page.getByText(LONG_URL, { exact: false }).first()).toBeVisible()
  await expectNoHorizontalScroll(page, 'memory?tab=approval')

  // Stapelleiste: liegt ganz im Viewport, die Seite bleibt ohne Seiten-Scroll.
  await page.getByRole('checkbox', { name: /Bestandskunden Nord bestellen/ }).check()
  const bar = page.getByRole('region', { name: /^(Auswahl|Selection)/ })
  await expect(bar).toBeVisible()
  const viewportWidth = page.viewportSize()?.width ?? 0
  const barBox = await bar.boundingBox()
  expect(barBox, 'Stapelleiste ohne Bounding-Box').not.toBeNull()
  expect(barBox!.x + barBox!.width).toBeLessThanOrEqual(viewportWidth + 1)
  await expectNoHorizontalScroll(page, 'memory?tab=approval (Stapelleiste offen)')

  // Gruppenfreigabe: Dialog passt in den Viewport.
  await page.getByRole('button', { name: new RegExp(`${agentName}`) }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const dialogBox = await dialog.boundingBox()
  expect(dialogBox!.x).toBeGreaterThanOrEqual(-1)
  expect(dialogBox!.x + dialogBox!.width).toBeLessThanOrEqual(viewportWidth + 1)
  await expectNoHorizontalScroll(page, 'memory?tab=approval (Gruppendialog)')
})

test('C5b-1: /memory „Einträge“ ohne Seiten-Scroll – Facetten, lange Zeile, Stapelleiste, Filter-Sheet', async ({
  page,
  request,
}) => {
  test.setTimeout(60_000)
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const agentName = 'E2E Vertriebsassistenz für Bestandskunden Nord und Süd'
  const agent = await apiRequest<{ id: string }>(
    request,
    token,
    `/v1/workspaces/${workspaceId}/agents`,
    { method: 'POST', data: { name: agentName } },
  )

  const now = '2026-10-03T08:00:00Z'
  const row = (id: string, fact: string, extra: Record<string, unknown> = {}) => ({
    id,
    agent_id: agent.id,
    status: 'active',
    fact,
    context: 'Aus dem Gespräch vom Vormittag.',
    category: 'fact',
    importance: 3,
    source: 'agent',
    triage_note: null,
    retrieval_count: 4,
    last_retrieved_at: now,
    created_at: now,
    updated_at: now,
    kind: 'agent_note',
    scope: 'agent',
    subject_user_id: null,
    origin: 'user_stated',
    created_by_agent_id: agent.id,
    occurrence_count: 1,
    confirmed_at: now,
    expires_at: null,
    ...extra,
  })
  const items = [
    row('e2e-entry-1', `Laut Wiki gilt die Preisliste ${LONG_URL} ab sofort für alle Kunden.`, {
      origin: 'external_content',
      confirmed_at: null,
      expires_at: '2026-10-08T08:00:00Z',
    }),
    row('e2e-entry-2', 'Rückfragen zu Lieferterminen gehen an die Logistik.', { status: 'expired' }),
    row('e2e-entry-3', 'Rabattstaffeln stehen im CRM unter Konditionen.'),
  ]
  const json = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
  await page.route(/\/v1\/workspaces\/[^/]+\/memories\/counts(\?|$)/, (route) =>
    route.fulfill(
      json({
        total: 1240,
        groups: {
          agent: { [agent.id]: 1240 },
          kind: { agent_note: 1200, user_fact: 30, lesson: 10 },
          status: { active: 1100, pending: 12, expired: 128 },
          health: { unconfirmed: 41, expiring_soon: 9, never_delivered: 300, stale_delivery: 3, external_or_inferred: 17 },
          origin: { user_stated: 900, inferred: 240, external_content: 100 },
          source: { agent: 1100, user: 140 },
        },
      }),
    ),
  )
  await page.route(/\/v1\/workspaces\/[^/]+\/memories(\?|$)/, (route) =>
    route.fulfill(json({ items, next_cursor: 'next' })),
  )
  await page.route(/\/v1\/workspaces\/[^/]+\/memory-proposals(\?|$)/, (route) =>
    route.fulfill(json([])),
  )

  await page.goto(`/w/${workspaceId}/memory?tab=entries`)
  await expect(page.getByTestId('entries-list')).toBeVisible()
  await expect(page.getByTestId('entry-row')).toHaveCount(3)
  // Der Verursacher muss gerendert sein, sonst misst die Probe blind gruen.
  await expect(page.getByText(LONG_URL, { exact: false }).first()).toBeVisible()
  await expectNoHorizontalScroll(page, 'memory?tab=entries')

  // Stapelleiste: liegt ganz im Viewport, die Seite bleibt ohne Seiten-Scroll.
  await page.getByRole('checkbox', { name: /Rabattstaffeln/ }).check()
  const bar = page.getByTestId('entries-bulk-bar')
  await expect(bar).toBeVisible()
  const viewportWidth = page.viewportSize()?.width ?? 0
  const barBox = await bar.boundingBox()
  expect(barBox, 'Stapelleiste ohne Bounding-Box').not.toBeNull()
  expect(barBox!.x + barBox!.width).toBeLessThanOrEqual(viewportWidth + 1)
  await expectNoHorizontalScroll(page, 'memory?tab=entries (Stapelleiste offen)')

  // Unter md: Facetten im Sheet (Filter-Standard §2.2); das Sheet passt in
  // den Viewport, und sein Panel scrollt nicht seitlich. Ab md gibt es keinen
  // Knopf — die Selects stehen im Raster der Leiste.
  const filterButton = page.getByRole('button', { name: /^(Filter|Filters)( \(|$)/ })
  if (viewportWidth < 768) {
    await expect(filterButton).toBeVisible()
  } else {
    await expect(filterButton).toBeHidden()
  }
  if (await filterButton.isVisible()) {
    await filterButton.click()
    const sheet = page.getByRole('dialog')
    await expect(sheet).toBeVisible()
    // Slide-in (`w2b-anim-sheet-*`, translate 100 % → 0) erst auslaufen lassen;
    // davor liegt die Box per Design noch rechts/unten ausserhalb. Gemessen
    // wird die ENDlage — passt die nicht, bleibt die Probe rot.
    await sheet.evaluate((el) =>
      Promise.all(el.getAnimations({ subtree: true }).map((a) => a.finished.catch(() => undefined))),
    )
    await expect(async () => {
      const sheetBox = await sheet.boundingBox()
      expect(sheetBox, 'Filter-Sheet ohne Bounding-Box').not.toBeNull()
      expect(sheetBox!.x).toBeGreaterThanOrEqual(-1)
      expect(sheetBox!.x + sheetBox!.width).toBeLessThanOrEqual(viewportWidth + 1)
      expect(sheetBox!.y + sheetBox!.height).toBeLessThanOrEqual((page.viewportSize()?.height ?? 0) + 1)
    }).toPass({ timeout: 5_000 })
    const panel = await page
      .getByTestId('list-filter-sheet-panel')
      .evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }))
    expect(panel.scroll, 'Filter-Sheet-Panel scrollt seitlich').toBeLessThanOrEqual(panel.client)
    await expectNoHorizontalScroll(page, 'memory?tab=entries (Filter-Sheet)')
  }
})
