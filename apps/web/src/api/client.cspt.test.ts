import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, createApi, type Api } from './client'

// CSPT-Schutz (Client-Side Path Traversal): kein Wert aus URL oder Daten darf
// den API-Pfad verlassen. Je Aufruf: Werte, die kein Pfadsegment sein koennen,
// werden ohne Netzabruf abgelehnt; alles andere landet als GENAU EIN kodiertes
// Segment an der erwarteten Stelle.

const WS = 'ws-1'
const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockImplementation(
    async () =>
      new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

interface Case {
  name: string
  call: (api: Api, value: string) => Promise<unknown>
  // Erwarteter Pfad fuer ein gueltiges Segment `seg` (bereits kodiert).
  expected: (seg: string) => string
}

const ws = `/v1/workspaces/${WS}`

const CASES: Case[] = [
  {
    name: 'getMemory',
    call: (api, v) => api.getMemory(v),
    expected: (s) => `${ws}/memories/${s}`,
  },
  {
    name: 'getPersona',
    call: (api, v) => api.getPersona(v),
    expected: (s) => `${ws}/personas/${s}`,
  },
  {
    name: 'exportPersona (markdown)',
    call: (api, v) => api.exportPersona(v, 'markdown'),
    expected: (s) => `${ws}/personas/${s}/export?format=markdown`,
  },
  {
    name: 'exportWaTable (Blob)',
    call: (api, v) => api.exportWaTable(v, 'csv'),
    expected: (s) => `${ws}/wa-tables/${s}/export?format=csv`,
  },
  {
    name: 'triageAgentMemory (zweites Segment)',
    call: (api, v) => api.triageAgentMemory('agent-1', v, { action: 'approve' } as never),
    expected: (s) => `${ws}/agents/agent-1/memories/${s}/triage`,
  },
  {
    name: 'getMemoryHistory (eigenes Gedaechtnis)',
    call: (api, v) => api.getMemoryHistory(null, v),
    expected: (s) => `${ws}/me/memories/${s}/history`,
  },
  {
    name: 'getTestReport (Version-ID)',
    call: (api, v) => api.getTestReport('persona', v),
    expected: (s) => `${ws}/versions/persona/${s}/test-report`,
  },
]

function pathOf(callIndex = 0): string {
  return String(fetchMock.mock.calls[callIndex][0]).replace(/^https?:\/\/[^/]+/, '')
}

describe.each(CASES)('CSPT: $name', ({ call, expected }) => {
  const api = createApi('tok', WS)

  it.each(['../x', 'a/b', '', '..', '.', 'a\\b', 'x?admin=1', 'x#frag'])(
    'lehnt %j ohne Netzabruf ab',
    async (value) => {
      await expect(call(api, value)).rejects.toBeInstanceOf(ApiError)
      expect(fetchMock).not.toHaveBeenCalled()
    },
  )

  it('setzt %2e%2e%2fx als ein kodiertes Segment ein', async () => {
    await call(api, '%2e%2e%2fx')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(pathOf()).toBe(expected('%252e%252e%252fx'))
  })

  it('laesst eine normale UUID unveraendert', async () => {
    const id = '3f2b8c1e-0000-4000-8000-000000000001'
    await call(api, id)
    expect(pathOf()).toBe(expected(id))
  })
})

describe('CSPT: Workspace-ID', () => {
  it('lehnt eine Workspace-ID mit Pfad-Trennern ohne Netzabruf ab', async () => {
    await expect(createApi('tok', '../../admin').listAgents()).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('weist den abgelehnten Aufruf als 404 aus (kein Ladefehler mit Retry)', async () => {
    await expect(createApi('tok', WS).getMemory('../x')).rejects.toMatchObject({ status: 404 })
  })
})

describe('CSPT: Query-Werte', () => {
  it('kodiert Query-Werte statt sie roh anzuhaengen', async () => {
    await createApi('tok', WS).listTokens({ agentId: 'a&scope=all' })
    expect(pathOf()).toBe(`${ws}/tokens?agent_id=a%26scope%3Dall`)
  })
})
