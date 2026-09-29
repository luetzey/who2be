import { expect, test } from '@playwright/test'

import { apiRequest, createUser, loginAs, seedWorkspace } from './helpers/auth'
import { decideCookieConsent } from './helpers/consent'
import { expectNoHorizontalScroll } from './helpers/viewport'

/**
 * Issue #624 (Owner-Entscheidung C, Audit E4 + A13): die primaere
 * Statusaktion einer Detailseite ist auf jedem Profil ohne Scrollen
 * erreichbar.
 *
 * Getragen wird das von zwei Dingen, beide hier belegt:
 * 1. Die Statusleiste steht auf allen Breakpoints oberhalb der Tabs
 *    (`docs/frontend/design-language.md` §4.4) — keine fixierte Bottom-Bar.
 * 2. Unterhalb `md` liegen die Sekundaeraktionen des Seitenkopfs (Feedback,
 *    Duplizieren, Export) hinter „Mehr" (`DetailHeader`). Ohne das rutscht
 *    „Publish" auf `mobile-320` (320×568) unter den Falz.
 *
 * Die Probe laeuft auf allen vier Profilen; `mobile-320` ist der scharfe
 * Fall. Selektoren nur ueber `data-testid`/Rollen ohne lokalisierten Text.
 */

test('#624: „Publish" steht im Status „In review" ohne Scrollen im Viewport', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`

  // Persona per API bis „In review" fuehren — Thema ist das Layout der
  // Detailseite, nicht der Anlage-Weg (den deckt journeys.spec.ts ab).
  // Tags und Beschreibung wie im Audit-Fall: ein realistisch voller Kopf.
  const persona = await apiRequest<{ id: string }>(request, token, `${base}/personas`, {
    method: 'POST',
    data: {
      name: 'E2E Review Viewport Persona',
      content: {
        description: 'Moderiert Feedbackgespraeche zwischen Teammitgliedern.',
        tags: ['coaching', 'feedback'],
        content: {
          blocks: [
            {
              id: 'e2e-body-p1',
              type: 'paragraph',
              props: {},
              content: [{ type: 'text', text: 'Profil', styles: {} }],
              children: [],
            },
          ],
        },
      },
    },
  })
  await apiRequest(request, token, `${base}/personas/${persona.id}/versions/1/transition`, {
    method: 'POST',
    data: { to: 'review' },
  })

  await page.goto(`/w/${workspaceId}/personas/${persona.id}`)
  const publish = page.getByTestId('branch-action-publish')
  await expect(publish).toBeVisible()
  await expectNoHorizontalScroll(page, 'personas/:id (Status review)')

  // Kein Scrollen: die Seite steht oben, der Knopf liegt vollstaendig im
  // Viewport (ratio 1 — ein halb abgeschnittener Knopf zaehlt nicht).
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
  await expect(publish).toBeInViewport({ ratio: 1 })

  // §4.4: Statusleiste oberhalb der Tabs, auf jedem Profil.
  const publishBox = await publish.boundingBox()
  const tabsBox = await page.getByRole('tablist').first().boundingBox()
  expect(publishBox, 'Publish ohne Bounding-Box').not.toBeNull()
  expect(tabsBox, 'Tabliste ohne Bounding-Box').not.toBeNull()
  expect(publishBox!.y + publishBox!.height).toBeLessThanOrEqual(tabsBox!.y)

  // Der Titel darf nicht neben die Aktionen gequetscht werden (CI-Befund auf
  // tablet-ipad-gen-7: ein Buchstabe je Zeile, „Publish" rutschte unter den
  // Falz). Die H1 muss mindestens ihr erstes Wort nebeneinander tragen.
  const h1Box = await page.getByRole('heading', { level: 1 }).boundingBox()
  expect(h1Box, 'H1 ohne Bounding-Box').not.toBeNull()
  expect(h1Box!.width).toBeGreaterThan(120)

  // Sekundaeraktionen: unterhalb `md` hinter „Mehr", darueber direkt sichtbar.
  const more = page.getByTestId('detail-header-more')
  const duplicate = page.getByTestId('duplicate-persona')
  const isPhone = (page.viewportSize()?.width ?? 0) < 768
  if (isPhone) {
    await expect(more).toBeVisible()
    await expect(more).toHaveAttribute('aria-expanded', 'false')
    await expect(duplicate).toBeHidden()
    await more.click()
    await expect(more).toHaveAttribute('aria-expanded', 'true')
    await expect(duplicate).toBeVisible()
    await expectNoHorizontalScroll(page, 'personas/:id (Mehr aufgeklappt)')
  } else {
    await expect(more).toBeHidden()
    await expect(duplicate).toBeVisible()
  }
})
