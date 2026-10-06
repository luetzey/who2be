import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

import { apiRequest, createUser, loginAs, seedWorkspace } from './helpers/auth'
import { decideCookieConsent } from './helpers/consent'
import { callMcpTool } from './helpers/mcp'

/**
 * Kernablauf „Agent configuration you review": eine Aenderung wird erst nach
 * Pruefung wirksam und kommt DANN beim Agenten an — belegt bis zum Abruf
 * ueber den echten MCP-Dienst des Compose-Stacks (`mcp`, :8765), nicht ueber
 * das REST-Aequivalent und nicht gemockt.
 *
 * Der Agent ist ein reiner Konsum-Agent (Default-Policy, keine
 * Schreib-Capability) mit eigenem `w2b_`-Token. Genau fuer diesen Aufrufer
 * gilt serverseitig `active_only = not ctx.sees_drafts(...)`
 * (`core/security.py`) — er darf nie eine ungepruefte Version sehen.
 *
 * Bedient wird die echte UI (Anlegen, Bearbeiten, Einreichen,
 * Veroeffentlichen). Selektoren wie in `journeys.spec.ts` ausschliesslich
 * ueber `data-testid`/`data-status` — keine lokalisierten Texte.
 */

interface McpPersona {
  persona: {
    id: string
    current_version: number
    current_status: string
    content: { description?: string }
  }
}

const statusBadge = (page: Page) =>
  page.locator('[data-testid="persona-status-badge"] [data-status]')

/** Was ein frisch verbundener Agent per MCP `get_persona` sieht. */
async function agentSees(
  request: APIRequestContext,
  agentToken: string,
  personaId: string,
): Promise<McpPersona['persona']> {
  const result = await callMcpTool(request, agentToken, 'get_persona', {
    identifier: personaId,
    format: 'full',
  })
  expect(result.isError, `get_persona meldete einen Tool-Fehler: ${result.text}`).toBe(false)
  return (JSON.parse(result.text) as McpPersona).persona
}

test('Review-Gate: nur gepruefte Versionen kommen per MCP beim Agenten an', async ({
  page,
  request,
}) => {
  // Mehr Stationen als die uebrigen Journeys (zwei Freigaben, vier
  // MCP-Abrufe mit je eigener Session) — 30 s Default reichen nicht sicher.
  test.setTimeout(120_000)

  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`

  // Konsum-Agent + Token. Eindeutige Texte je Version, damit ein Treffer
  // nicht zufaellig aus der anderen Version stammen kann.
  const agent = await apiRequest<{ id: string }>(request, token, `${base}/agents`, {
    method: 'POST',
    data: { name: 'E2E Review-Gate Reader' },
  })
  const { token: agentToken } = await apiRequest<{ token: string }>(
    request,
    token,
    `${base}/tokens`,
    { method: 'POST', data: { name: 'e2e-review-gate', agent_id: agent.id } },
  )
  const textV1 = `Review-Gate v1 ${crypto.randomUUID()}`
  const textV2 = `Review-Gate v2 ${crypto.randomUUID()}`

  // --- 1. Anlegen → v1 einreichen → pruefen → veroeffentlichen -------------
  await page.goto(`/w/${workspaceId}/personas/new`)
  await page.getByTestId('persona-name-input').fill('E2E Review-Gate Persona')
  await page.getByTestId('persona-description-input').fill(textV1)
  // Promote-Validierung verlangt einen nicht-leeren Profil-Body.
  await page.getByTestId('persona-profile-editor').click()
  await page.keyboard.type('E2E Profil-Body')
  await page.getByTestId('persona-new-submit').click()
  await page.waitForURL(/\/w\/[^/]+\/personas\/(?!new$)[^/]+$/)
  const personaId = page.url().split('/').pop() as string

  await expect(statusBadge(page)).toHaveAttribute('data-status', 'draft')
  // Negativprobe UI: aus draft bietet die Oberflaeche kein Veroeffentlichen an.
  await expect(page.getByTestId('branch-action-submit')).toBeVisible()
  await expect(page.getByTestId('branch-action-publish')).toHaveCount(0)

  await page.getByTestId('branch-action-submit').click()
  await expect(statusBadge(page)).toHaveAttribute('data-status', 'review')

  // Noch nie veroeffentlicht: der Agent sieht die Persona gar nicht.
  const beforePublish = await callMcpTool(request, agentToken, 'get_persona', {
    identifier: personaId,
    format: 'text',
  })
  // Genau „nicht gefunden" (serverseitiger active-only-Filter) — nicht
  // irgendein Fehler, sonst liesse ein Auth-Problem die Probe gruen.
  expect(beforePublish.isError).toBe(true)
  expect(beforePublish.text).toContain('persona_not_found')

  await page.getByTestId('branch-action-publish').click()
  await expect(statusBadge(page)).toHaveAttribute('data-status', 'active')

  const afterV1 = await agentSees(request, agentToken, personaId)
  expect(afterV1.current_version).toBe(1)
  expect(afterV1.current_status).toBe('active')
  expect(afterV1.content.description).toBe(textV1)

  // --- 2. v2 mit geaendertem Text anlegen und einreichen -------------------
  // Bearbeiten einer aktiven Persona legt per Auto-Save einen Draft v2 an.
  await page.getByTestId('persona-description-input').fill(textV2)
  await expect(statusBadge(page)).toHaveAttribute('data-status', 'draft')
  await page.getByTestId('branch-action-submit').click()
  await expect(statusBadge(page)).toHaveAttribute('data-status', 'review')

  // Der Mensch sieht v2 im Review — der Agent bekommt es NICHT.
  const human = await apiRequest<{ current_version: number; content: { description?: string } }>(
    request,
    token,
    `${base}/personas/${personaId}`,
  )
  expect(human.current_version).toBe(2)
  expect(human.content.description).toBe(textV2)

  const duringReview = await agentSees(request, agentToken, personaId)
  expect(duringReview.current_version).toBe(1)
  expect(duringReview.current_status).toBe('active')
  expect(duringReview.content.description).toBe(textV1)
  expect(duringReview.content.description).not.toBe(textV2)

  // --- 3. v2 veroeffentlichen → Agent bekommt v2 --------------------------
  await page.getByTestId('branch-action-publish').click()
  await expect(statusBadge(page)).toHaveAttribute('data-status', 'active')

  const afterV2 = await agentSees(request, agentToken, personaId)
  expect(afterV2.current_version).toBe(2)
  expect(afterV2.current_status).toBe('active')
  expect(afterV2.content.description).toBe(textV2)
})

test('Review-Gate: draft → active direkt lehnt die API ab', async ({ request }) => {
  const user = await createUser(request)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const base = `/v1/workspaces/${workspaceId}`

  const persona = await apiRequest<{ id: string }>(request, token, `${base}/personas`, {
    method: 'POST',
    data: {
      name: 'E2E Draft-Shortcut Persona',
      content: {
        description: 'Draft-Shortcut',
        content: {
          blocks: [
            {
              id: 'e2e-body-p1',
              type: 'paragraph',
              props: {},
              content: [{ type: 'text', text: 'Draft-Shortcut', styles: {} }],
              children: [],
            },
          ],
        },
      },
    },
  })

  // Admin mit aal2 und vollstaendigem Inhalt: nur die State-Machine sperrt.
  const response = await request.post(
    `${process.env.E2E_API_BASE_URL ?? 'http://localhost:8000'}${base}/personas/${persona.id}/versions/1/transition`,
    { headers: { Authorization: `Bearer ${token}` }, data: { to: 'active' } },
  )
  expect(response.status()).toBe(409)
  expect(((await response.json()) as { reason?: string }).reason).toBe('forbidden_transition')

  const after = await apiRequest<{ current_status: string }>(
    request,
    token,
    `${base}/personas/${persona.id}`,
  )
  expect(after.current_status).toBe('draft')
})
