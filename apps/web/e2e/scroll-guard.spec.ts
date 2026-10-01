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

  // --- Feedback geben: oeffnen, ausfuellen, absenden, zurueck mit Bestaetigung.
  await page.getByRole('link', { name: giveName }).click()
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
  await page.getByRole('link', { name: giveName }).click()
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
  const routes: Array<[string, string, number, RegExp]> = [
    [`${ws}/agents/${agent.id}`, 'agents/:id', 3, /.+/],
    [`${ws}/resources/${resource.id}`, 'resources/:id', 4, detailView],
    [`${ws}/personas/${persona.id}`, 'personas/:id', 5, detailView],
  ]

  const failures: string[] = []
  for (const [path, label, tabCount, expectedName] of routes) {
    await page.goto(path)
    const tablist = page.getByRole('tablist').first()
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
