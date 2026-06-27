/**
 * Web-Client ↔ OpenAPI-Contract (ADR-0032, Phase 3).
 *
 * Faengt Drift zwischen dem Frontend-API-Client und der echten Backend-Surface:
 * jeder Pfad, den `createApi`/die Modul-Exports aufrufen, muss im
 * OpenAPI-Golden (`apps/api/tests/contract/openapi_surface.json`, vom
 * Python-Contract-Test erzeugt) existieren. Wir mocken `fetch`, rufen *jede*
 * Methode auf, normalisieren dynamische Segmente zu `{}` und vergleichen.
 *
 * Robust gegen Parameter-Namen: sowohl die aufgezeichneten Pfade als auch die
 * OpenAPI-Pfade werden auf `{}` normalisiert (Sentinel-Segmente bzw. `{name}`).
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { acceptInvitation, createApi, fetchMe } from './client'

// Distinktive Sentinels fuer dynamische Pfad-Segmente. Jedes Segment, das exakt
// einem Sentinel entspricht, wird beim Normalisieren zu `{}`.
const WS = '__WS__'
const ID = '__ID__'
// `playbook` ist der `entity_type`-Pfadparameter der Feedback-Routen (OpenAPI
// `{entity_type}`) — als Sentinel normalisiert, damit der Literal nicht den
// Golden-Vergleich bricht.
const SENTINELS = new Set([WS, ID, '7', 'tok-plain', '__USER__', '__ORG__', 'playbook'])

// Cloud-only Endpoints (ADR-0029): per `_register_billing_if_present` nur in der
// Cloud-Edition gemountet und im On-Prem-Web-Bundle tree-geshaked. Das On-Prem-
// OpenAPI-Golden enthaelt sie bewusst nicht — daher hier vom Drift-Check ausgenommen.
const CLOUD_ONLY = new Set(['POST /v1/workspaces/{}/billing/checkout'])

const here = path.dirname(fileURLToPath(import.meta.url))
const goldenPath = path.resolve(
  here,
  '../../../../apps/api/tests/contract/openapi_surface.json',
)

interface SurfaceEntry {
  method: string
  path: string
}

function normalize(p: string): string {
  const noQuery = p.split('?')[0]
  return noQuery
    .split('/')
    .map((seg) => (SENTINELS.has(seg) || /^\{[^}]+\}$/.test(seg) ? '{}' : seg))
    .join('/')
}

const calls: Array<{ method: string; path: string }> = []

beforeEach(() => {
  calls.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      // `config.apiBaseUrl` ist im Test leer → url ist bereits der Pfad.
      const pathOnly = url.replace(/^https?:\/\/[^/]+/, '')
      calls.push({ method: (init?.method ?? 'GET').toUpperCase(), path: pathOnly })
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('jeder vom Web-Client genutzte Pfad existiert im OpenAPI-Golden', async () => {
  const api = createApi('token', WS)

  // Alle Api-Methoden mit Sentinel-Argumenten aufrufen (Inputs minimal — der
  // Recorder braucht nur Methode + Pfad). Promises sammeln und awaiten.
  const invocations: Array<Promise<unknown>> = [
    fetchMe('token'),
    acceptInvitation('token', 'tok-plain'),
    api.listPersonas(),
    api.getPersona(ID),
    api.createPersona({} as never),
    api.updatePersona(ID, {} as never),
    api.patchPersonaDraft(ID, {} as never),
    api.patchPlaybookDraft(ID, {} as never),
    api.patchResourceDraft(ID, {} as never),
    api.listPersonaVersions(ID),
    api.listPersonaTags(),
    api.listPersonaPlaybooks(ID),
    api.setPersonaPlaybooks(ID, []),
    api.listPlaybooks(),
    api.getPlaybook(ID),
    api.createPlaybook({} as never),
    api.updatePlaybook(ID, {} as never),
    api.listPlaybookVersions(ID),
    api.listPlaybookTags(),
    api.listTokens(),
    api.createToken({} as never),
    api.revokeToken(ID),
    api.getDashboard(),
    api.getFeedback('playbook', ID),
    api.getFeedbackEvents('playbook', ID),
    api.getFeedbackOverview(),
    api.getFeedbackUnused(),
    api.transitionPersonaVersion(ID, 7, 'active'),
    api.transitionPlaybookVersion(ID, 7, 'active'),
    api.listResources(),
    api.getResource(ID),
    api.createResource({} as never),
    api.updateResource(ID, {} as never),
    api.listResourceVersions(ID),
    api.transitionResourceVersion(ID, 7, 'active'),
    api.listPlaybookResourceLinks(ID),
    api.setPlaybookResourceLinks(ID, []),
    api.getPlaybookUsages(ID),
    api.getResourceUsages(ID),
    api.listResourceSubResources(ID),
    api.setResourceSubResources(ID, []),
    api.listResourceUsedBy(ID),
    api.listPlaybookComposes(ID),
    api.setPlaybookComposes(ID, []),
    api.listPlaybookComposedBy(ID),
    api.listResourceTags(),
    api.listResourcesByTag('tag'),
    api.listMembers(),
    api.updateMemberRole('__USER__', {} as never),
    api.removeMember('__USER__'),
    api.listInvitations(),
    api.createInvitation({} as never),
    api.revokeInvitation(ID),
    api.createOrganization({} as never),
    api.listOrgWorkspaces('__ORG__'),
    api.createWorkspace('__ORG__', {} as never),
    api.renameWorkspace(WS, {} as never),
    api.deleteWorkspace(WS),
    api.deleteAccount(),
    api.deleteOrganization('__ORG__'),
    api.exportMyData(),
    api.listSystemPromptTemplates(),
    api.getSystemPromptTemplate(ID),
    api.createSystemPromptTemplate({} as never),
    api.updateSystemPromptTemplate(ID, {} as never),
    api.listSystemPromptTemplateVersions(ID),
    api.transitionSystemPromptTemplateVersion(ID, 7, 'active'),
    api.restorePersonaVersion(ID, 7),
    api.diffPersonaVersion(ID, 7),
    api.provenancePersonaVersion(ID, 7),
    api.restorePlaybookVersion(ID, 7),
    api.diffPlaybookVersion(ID, 7),
    api.provenancePlaybookVersion(ID, 7),
    api.restoreResourceVersion(ID, 7),
    api.diffResourceVersion(ID, 7),
    api.provenanceResourceVersion(ID, 7),
    api.restoreSystemPromptTemplateVersion(ID, 7),
    api.diffSystemPromptTemplateVersion(ID, 7),
    api.provenanceSystemPromptTemplateVersion(ID, 7),
    api.listAgents(),
    api.getAgent(ID),
    api.createAgent({} as never),
    api.updateAgent(ID, {} as never),
    api.deleteAgent(ID),
    api.copyAgent(ID),
    api.renderAgentPrompt(ID),
    api.previewPlaceholder({ kind: 'playbook', target_id: ID } as never),
    api.getEntitlement(),
    api.createCheckout({} as never),
  ]
  await Promise.all(invocations)

  const golden = JSON.parse(readFileSync(goldenPath, 'utf-8')) as SurfaceEntry[]
  const goldenSet = new Set(golden.map((e) => `${e.method} ${normalize(e.path)}`))

  const missing = calls
    .map((c) => `${c.method} ${normalize(c.path)}`)
    .filter((key) => !goldenSet.has(key) && !CLOUD_ONLY.has(key))

  // Mindestens die volle Surface sollte abgedeckt sein (Sanity gegen leere Calls).
  expect(calls.length).toBeGreaterThan(70)
  expect(
    [...new Set(missing)],
    'Web-Client ruft Pfade auf, die nicht im OpenAPI-Golden existieren — ' +
      'Drift zwischen Frontend und Backend.',
  ).toEqual([])
})
