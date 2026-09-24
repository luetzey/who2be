import { expect, test } from '@playwright/test'

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
  // K3 ROT-PROBE — wird nach dem Beleglauf zurueckgenommen.
  // Bricht absichtlich NUR auf schmalen Viewports, damit der Beleg trennscharf
  // ist: `e2e` (chromium, 1280px) bleibt gruen, nur `e2e-mobile` faellt.
  const width = page.viewportSize()?.width ?? 1280
  const extra = width <= 834 ? ';width:calc(100% + 200px)' : ''
  await page.setContent(
    PAGE_SHELL(`<div style="width:100%;height:200px${extra}" data-testid="ok-block">Inhalt</div>`),
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
