import { expect, test } from '@playwright/test'

import {
  apiRequest,
  createUser,
  loginAs,
  seedWorkspace,
  SESSION_STORAGE_KEY,
} from './helpers/auth'

/**
 * Kritische User-Journeys (ADR-0041, Phase 4 — duenne Spitze, 4 Pfade) gegen
 * den laufenden Compose-Stack (Web :5173, API :8000, GoTrue via Gateway :9999).
 *
 * Auth/Seed: `./helpers/auth.ts` — Signup mit Autoconfirm liefert die Session
 * direkt; `loginAs` injiziert sie via `sessionStorage['who2be.auth.session']`
 * (exakter storageKey aus `src/lib/supabase.ts`), `seedWorkspace` nutzt den
 * Lazy-Seed von `GET /v1/me` (User = admin seines Personal-Workspace).
 *
 * Selektoren ausschliesslich ueber `data-testid`/`data-status` — keine
 * lokalisierten Texte.
 */

interface PersonaRead {
  id: string
  current_version: number
  current_status: string
  content: { description?: string }
}

test('Persona-Lifecycle: anlegen (Draft) -> Draft->Review->Active', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  await loginAs(page, user)
  const { workspaceId } = await seedWorkspace(request, user)

  await page.goto(`/w/${workspaceId}/personas/new`)
  await page.getByTestId('persona-name-input').fill('E2E Lifecycle Persona')
  await page.getByTestId('persona-description-input').fill('Beschreibung v1')
  // Promote-Validierung (draft->review) verlangt einen nicht-leeren Body
  // (content.content.blocks) — ohne Profil-Text bleibt der Submit ein 409.
  await page.getByTestId('persona-profile-editor').click()
  await page.keyboard.type('E2E Profil-Body v1')
  await page.getByTestId('persona-new-submit').click()

  await page.waitForURL(/\/w\/[^/]+\/personas\/[^/]+$/)
  await expect(page.getByTestId('persona-status-badge')).toBeVisible()
  await expect(page.locator('[data-testid="persona-status-badge"] [data-status]')).toHaveAttribute(
    'data-status',
    'draft',
  )

  // Draft -> Review (BranchStatus-Action, Testid-Schema branch-action-<key>).
  await page.getByTestId('branch-action-submit').click()
  await expect(page.getByTestId('branch-action-publish')).toBeVisible()

  // Review -> Active (Promote ist admin-only; der Personal-WS-User ist admin).
  await page.getByTestId('branch-action-publish').click()
  await expect(
    page.locator('[data-testid="persona-status-badge"] [data-status]'),
  ).toHaveAttribute('data-status', 'active')
})

test('Playbook->Resource-Block-Ref erzeugt Backlink in Resource-Detail', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  await loginAs(page, user)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token

  // Resource per API seeden (deterministische ID); die Editor-Interaktion —
  // der eigentliche Kern der Journey — laeuft danach durch die echte UI.
  // Mit Heading-Block: der ResourcePicker rendert die Block-Optionen (inkl.
  // "Gesamtes Dokument") nur, wenn die Resource Heading-Bloecke hat.
  const resource = await apiRequest<{ id: string }>(
    request,
    token,
    `/v1/workspaces/${workspaceId}/resources`,
    {
      method: 'POST',
      data: {
        name: 'E2E Backlink Resource',
        content: {
          description: 'E2E Backlink-Ziel',
          blocks: [
            {
              id: 'e2e-h1',
              type: 'heading',
              props: { level: 2 },
              content: [{ type: 'text', text: 'Abschnitt A', styles: {} }],
              children: [],
            },
            {
              id: 'e2e-p1',
              type: 'paragraph',
              props: {},
              content: [{ type: 'text', text: 'Inhalt A', styles: {} }],
              children: [],
            },
          ],
        },
      },
    },
  )

  await page.goto(`/w/${workspaceId}/playbooks/new`)
  await page.getByTestId('playbook-name-input').fill('E2E Backlink Playbook')
  // Description ist required (native HTML-Validierung) — ohne Wert blockt der
  // Submit still und die waitForURL-Navigation kommt nie.
  await page.getByTestId('playbook-description-input').fill('E2E Backlink Beschreibung')

  // BlockNote-Slash-Menue: Drittanbieter-UI ohne Testids — Tastatur-Simulation
  // (kein Text-Locator): Editor fokussieren, `/resource` tippen, Enter waehlt
  // den einzig verbleibenden gefilterten Eintrag.
  await page.getByTestId('playbook-body-editor').click()
  await page.keyboard.type('/resource')
  await page.keyboard.press('Enter')

  // Der ResourcePicker hat vollstaendige, ID-basierte Testids.
  await page.getByTestId(`resource-option-${resource.id}`).click()
  await page.getByTestId('resource-block-option-whole').click()
  await page.getByTestId('resource-picker-confirm').click()

  await page.getByTestId('playbook-new-submit').click()
  // `(?!new$)`: /playbooks/new matcht das Segment-Muster ebenfalls — ohne den
  // Ausschluss "wartete" der erste echte CI-Lauf gar nicht und las `new` als ID.
  await page.waitForURL(/\/w\/[^/]+\/playbooks\/(?!new$)[^/]+$/)
  const playbookId = page.url().split('/').pop() as string

  await page.goto(`/w/${workspaceId}/resources/${resource.id}`)
  await page.getByTestId('tab-use').click()
  await expect(page.getByTestId(`used-by-item-${playbookId}`)).toBeVisible()
})

test('Agent-Read liefert nur die aktive Version (MCP-Aequivalent)', async ({ request }) => {
  // MCP-HTTP (ADR-0034/0036) braeuchte den vollen OAuth-2.1-Consent-Flow.
  // Ein Agent-Token (`w2b_...`) laeuft ueber dieselbe serverseitige Policy
  // (`active_only = not ctx.sees_drafts(...)`, persona_service.py), die auch
  // das MCP-Tool `get_persona` durchsetzt — REST-Aequivalent, im
  // Repo-Pflege-Plan ausdruecklich genehmigt.
  const user = await createUser(request)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`

  // Body-Blocks noetig: die Promote-Validierung (draft->review/active)
  // verlangt name + description + nicht-leere content.content.blocks.
  const personaBody = (text: string) => ({
    description: text,
    content: {
      blocks: [
        {
          id: 'e2e-body-p1',
          type: 'paragraph',
          props: {},
          content: [{ type: 'text', text, styles: {} }],
          children: [],
        },
      ],
    },
  })
  const persona = await apiRequest<PersonaRead>(request, token, `${base}/personas`, {
    method: 'POST',
    data: { name: 'E2E Active-Read Persona', content: personaBody('X v1') },
  })
  await apiRequest(request, token, `${base}/personas/${persona.id}/versions/1/transition`, {
    method: 'POST',
    data: { to: 'review' },
  })
  await apiRequest(request, token, `${base}/personas/${persona.id}/versions/1/transition`, {
    method: 'POST',
    data: { to: 'active' },
  })
  // Draft v2 anlegen, aktive v1 bleibt unveraendert.
  await apiRequest(request, token, `${base}/personas/${persona.id}`, {
    method: 'PUT',
    data: { name: 'E2E Active-Read Persona', content: personaBody('X v2') },
  })

  const agent = await apiRequest<{ id: string }>(request, token, `${base}/agents`, {
    method: 'POST',
    data: { name: 'E2E Reader' },
  })
  const agentToken = await apiRequest<{ token: string }>(request, token, `${base}/tokens`, {
    method: 'POST',
    data: { name: 'e2e-reader-token', agent_id: agent.id },
  })

  const seen = await apiRequest<PersonaRead>(
    request,
    agentToken.token,
    `${base}/personas/${persona.id}`,
  )
  expect(seen.content.description).toBe('X v1')
  expect(seen.content.description).not.toBe('X v2')
})

test('Invitation-Accept inkl. Email-Mismatch-Guard', async ({ browser, request }) => {
  const admin = await createUser(request)
  const { workspaceId } = await seedWorkspace(request, admin)
  const wrongUser = await createUser(request)
  const rightUser = await createUser(request)

  // Klartext-Token kommt im 201-Body zurueck (InvitationCreated) — keine
  // Mailbox noetig; die Accept-Page hat den manuellen Button-Flow.
  const invitation = await apiRequest<{ token: string }>(
    request,
    admin.session.access_token,
    `/v1/workspaces/${workspaceId}/invitations`,
    { method: 'POST', data: { email: rightUser.email, role: 'editor' } },
  )

  // Falsche Email: Guard blockt, kein Redirect. Eigener BrowserContext pro
  // Rolle — sauberer als zweifaches Einloggen derselben Page.
  const wrongContext = await browser.newContext()
  const wrongPage = await wrongContext.newPage()
  await loginAs(wrongPage, wrongUser)
  await wrongPage.goto(`/invitations/${invitation.token}/accept`)
  await wrongPage.getByTestId('invitation-accept-submit').click()
  await expect(wrongPage.getByTestId('error-alert')).toBeVisible()
  expect(wrongPage.url()).toContain(`/invitations/${invitation.token}/accept`)
  await wrongContext.close()

  // Korrekte Email: Beitritt + Redirect in den Workspace.
  const rightContext = await browser.newContext()
  const rightPage = await rightContext.newPage()
  await loginAs(rightPage, rightUser)
  await rightPage.goto(`/invitations/${invitation.token}/accept`)
  await rightPage.getByTestId('invitation-accept-submit').click()
  await rightPage.waitForURL(/\/w\/.+/)
  await rightContext.close()
})


test('Angemeldet bleiben: neuer Tab bleibt eingeloggt (Issue #430 AC 1)', async ({
  page,
  context,
  request,
}) => {
  const user = await createUser(request)
  const { workspaceId } = await seedWorkspace(request, user)

  // "Angemeldet bleiben"-Session direkt injizieren: derselbe Zustand, den ein
  // echter Login MIT gesetztem Haken hinterlaesst (Session in `localStorage`
  // statt `sessionStorage`, plus die beiden Flags aus `lib/supabase.ts` /
  // `SessionProvider.tsx`). Passwort-Login + TOTP-Step-up haben eigene
  // Vitest-Abdeckung (LoginPage.test.tsx) -- diese Journey testet
  // ausschliesslich die Tab-/Neustart-Persistenz.
  const signedInAt = Date.now() - 60_000 // 1 Minute alt, weit innerhalb der Default-Obergrenze (12 h)
  await page.addInitScript(
    ([sessionKey, sessionJson, rememberKey, signedInAtKey, signedInAtValue]) => {
      window.localStorage.setItem(sessionKey, sessionJson)
      window.localStorage.setItem(rememberKey, 'true')
      window.localStorage.setItem(signedInAtKey, signedInAtValue)
    },
    [
      SESSION_STORAGE_KEY,
      JSON.stringify(user.session),
      'who2be.auth.remember',
      'who2be.auth.signed_in_at',
      String(signedInAt),
    ] as const,
  )

  await page.goto(`/w/${workspaceId}`)
  // Eingeloggt: `WorkspaceIndexRedirect` landet auf dem Dashboard. Ohne
  // erkannte Session wuerde `RequireAuth` stattdessen auf `/login` schicken.
  await page.waitForURL(/\/w\/[^/]+\/dashboard$/)

  // Neuer Tab IM SELBEN Browser-Context = dieselbe Storage-Partition wie
  // echte Tabs eines Chrome-Profils: `localStorage` wird geteilt,
  // `sessionStorage` nicht -- genau der Mechanismus, den AC 1 verlangt (kein
  // erneuter Login, kein TOTP-Prompt).
  const secondTab = await context.newPage()
  await secondTab.goto(`/w/${workspaceId}`)
  await secondTab.waitForURL(/\/w\/[^/]+\/dashboard$/)
  await secondTab.close()
})

test('Angemeldet bleiben: abgelaufene Session verlangt vollen Login (Issue #430 AC 1)', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  const { workspaceId } = await seedWorkspace(request, user)

  // Zeitstempel weit VOR der Default-Obergrenze (12 h) -- `SessionProvider`
  // muss das beim Boot erkennen, die Session verwerfen und auf `/login`
  // schicken, statt sie zu committen.
  const signedInAt = Date.now() - 13 * 60 * 60 * 1000
  await page.addInitScript(
    ([sessionKey, sessionJson, rememberKey, signedInAtKey, signedInAtValue]) => {
      window.localStorage.setItem(sessionKey, sessionJson)
      window.localStorage.setItem(rememberKey, 'true')
      window.localStorage.setItem(signedInAtKey, signedInAtValue)
    },
    [
      SESSION_STORAGE_KEY,
      JSON.stringify(user.session),
      'who2be.auth.remember',
      'who2be.auth.signed_in_at',
      String(signedInAt),
    ] as const,
  )

  await page.goto(`/w/${workspaceId}`)
  await page.waitForURL(/\/login/)
})
