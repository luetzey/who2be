import { expect, test } from '@playwright/test'

import { apiRequest, createUser, loginAs, seedWorkspace } from './helpers/auth'

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
  const resource = await apiRequest<{ id: string }>(
    request,
    token,
    `/v1/workspaces/${workspaceId}/resources`,
    { method: 'POST', data: { name: 'E2E Backlink Resource' } },
  )

  await page.goto(`/w/${workspaceId}/playbooks/new`)
  await page.getByTestId('playbook-name-input').fill('E2E Backlink Playbook')

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
  await page.waitForURL(/\/w\/[^/]+\/playbooks\/([^/]+)$/)
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

  const persona = await apiRequest<PersonaRead>(request, token, `${base}/personas`, {
    method: 'POST',
    data: { name: 'E2E Active-Read Persona', content: { description: 'X v1' } },
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
    data: { name: 'E2E Active-Read Persona', content: { description: 'X v2' } },
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
