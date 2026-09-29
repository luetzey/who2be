import { expect, test, type Page } from '@playwright/test'

import { createUser, loginAs, seedWorkspace } from './helpers/auth'
import { decideCookieConsent } from './helpers/consent'
import { expectNoHorizontalScroll } from './helpers/viewport'

/**
 * App-Navigation in Gruppen (Audit E2-B, Owner-Entscheidung E2 = B).
 *
 * Oben Dashboard + Agents, dann "Building blocks" (System prompts, Personas,
 * Playbooks, Resources, External tools), dann "Operations" (Work area,
 * Feedback), zuletzt Settings. Gilt fuer die Desktop-Sidebar UND das
 * Phone-Sheet — welche Flaeche gilt, entscheidet der Viewport des
 * Playwright-Projekts (Sidebar ab `md` = 768 px, darunter das Sheet).
 *
 * Selektoren ueber `data-testid` (Repo-Konvention, siehe journeys.spec.ts):
 * die Gruppen-IDs und Link-IDs sind sprachunabhaengig. Die Ueberschriften
 * selbst sind nur ueber ihre Anzahl und ihre Verknuepfung mit der Liste
 * (`aria-labelledby`) geprueft, nicht ueber ihren Text.
 */

const GROUPS: { id: string; titled: boolean; links: string[] }[] = [
  { id: 'main', titled: false, links: ['dashboard', 'agents'] },
  {
    id: 'building-blocks',
    titled: true,
    links: ['systemPrompts', 'personas', 'playbooks', 'resources', 'tools'],
  },
  { id: 'operations', titled: true, links: ['workarea', 'feedback'] },
  { id: 'settings', titled: false, links: ['settings'] },
]

// Tailwind-`md` (design-language §4.4): ab hier Sidebar, darunter Sheet.
const MD_BREAKPOINT_PX = 768

// Unveraenderte Routen je Link (Audit E2-B: "Routen bleiben unveraendert").
const ROUTES: Record<string, RegExp> = {
  dashboard: /\/dashboard$/,
  agents: /\/agents$/,
  systemPrompts: /\/system-prompts$/,
  personas: /\/personas$/,
  playbooks: /\/playbooks$/,
  resources: /\/resources$/,
  tools: /\/tools$/,
  workarea: /\/workarea$/,
  feedback: /\/feedback$/,
  settings: /\/settings\/account$/,
}

/**
 * Oeffnet auf schmalen Viewports das Sheet und liefert die sichtbare Nav.
 * Die Flaeche folgt der `md`-Schwelle (design-language §4.4) — entschieden
 * ueber die Viewport-Breite, nicht ueber `isVisible()` des Triggers: das
 * wartet nicht und liefe vor dem ersten Render in einen Rennzustand.
 */
async function visibleNav(page: Page) {
  const width = page.viewportSize()?.width ?? 1280
  if (width < MD_BREAKPOINT_PX) {
    await page.getByTestId('app-nav-open').click()
    const nav = page.getByTestId('app-nav-sheet')
    await expect(nav).toBeVisible()
    return nav
  }
  await expect(page.getByTestId('app-nav-open')).toBeHidden()
  const nav = page.getByTestId('app-nav-sidebar')
  await expect(nav).toBeVisible()
  return nav
}

test('Navigation zeigt Gruppen in fester Reihenfolge, benannt per Ueberschrift', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)

  await page.goto(`/w/${workspaceId}/dashboard`)
  const nav = await visibleNav(page)
  await expectNoHorizontalScroll(page, 'App-Navigation (Sidebar bzw. Sheet)')

  const lists = nav.locator('ul[data-testid^="nav-group-"]')
  await expect(lists).toHaveCount(GROUPS.length)
  for (const [index, group] of GROUPS.entries()) {
    const list = lists.nth(index)
    await expect(list).toHaveAttribute('data-testid', `nav-group-${group.id}`)
    const links = list.locator('a[data-testid^="nav-link-"]')
    await expect(links).toHaveCount(group.links.length)
    for (const [linkIndex, key] of group.links.entries()) {
      await expect(links.nth(linkIndex)).toHaveAttribute('data-testid', `nav-link-${key}`)
      await expect(links.nth(linkIndex)).toBeVisible()
    }
    if (group.titled) {
      // Die Liste ist ueber ihre sichtbare Ueberschrift benannt.
      const headingId = await list.getAttribute('aria-labelledby')
      expect(headingId, `Gruppe ${group.id} ohne aria-labelledby`).toBeTruthy()
      const heading = nav.locator(`h2[id="${headingId}"]`)
      await expect(heading).toBeVisible()
      await expect(heading).not.toHaveText('')
    } else {
      await expect(list).not.toHaveAttribute('aria-labelledby', /.+/)
    }
  }
  await expect(nav.locator('h2')).toHaveCount(GROUPS.filter((g) => g.titled).length)
})

test('Navigation erreicht jedes Ziel unter unveraenderter Route', async ({ page, request }) => {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)

  await page.goto(`/w/${workspaceId}/dashboard`)
  for (const key of GROUPS.flatMap((g) => g.links)) {
    const nav = await visibleNav(page)
    await nav.getByTestId(`nav-link-${key}`).click()
    await expect(page).toHaveURL(ROUTES[key])
    // Auf dem Phone schliesst das Sheet nach der Wahl (Issue #500).
    await expect(page.getByTestId('app-nav-sheet')).toHaveCount(0)
  }
})

test('Navigation ist per Tastatur in Gruppenreihenfolge erreichbar', async ({ page, request }) => {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)

  await page.goto(`/w/${workspaceId}/dashboard`)
  const nav = await visibleNav(page)
  const expected = GROUPS.flatMap((g) => g.links).map((key) => `nav-link-${key}`)

  // Fokus auf den ersten Link, dann mit Tab durch die Nav: die Reihenfolge
  // muss der Gruppenfolge entsprechen (keine Ueberschrift ist fokussierbar,
  // kein Link springt heraus).
  await nav.getByTestId(expected[0]).focus()
  const seen: (string | null)[] = []
  for (let i = 0; i < expected.length; i += 1) {
    seen.push(await page.evaluate(() => document.activeElement?.getAttribute('data-testid') ?? null))
    await page.keyboard.press('Tab')
  }
  expect(seen).toEqual(expected)
})
