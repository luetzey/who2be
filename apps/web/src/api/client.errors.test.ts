/**
 * Fehler- und Randpfade des API-Clients (Coverage-Abtrag WP-1/TST-1).
 *
 * Ergaenzt `client.test.ts` (Happy-Path-Basics) und `client.contract.test.ts`
 * (Pfad-Drift gegen das OpenAPI-Golden) um die Branches, die dort bewusst
 * nicht laufen: Non-OK-Statuscodes, problem+json- vs. Plain-Text-Bodies,
 * DeleteBlocked-409, 204/leere Bodies, Query-Param-Bau, Token-/Header-
 * Handling, Text-Exporte (`requestText`) und bislang untestierte Methoden.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import i18n, { DEFAULT_LOCALE } from '@/i18n'

import { acceptInvitation, ApiError, createApi, fetchMe, oauthConsent } from './client'

const WS = 'ws-err'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function problemResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/problem+json' },
  })
}

// Factory statt fester Response: ein Response-Body ist nur einmal lesbar,
// Tests mit mehreren Calls brauchen pro Call eine frische Instanz.
function stubFetch(factory: () => Response): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(factory()))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function lastCall(fetchMock: ReturnType<typeof vi.fn>): [string, RequestInit | undefined] {
  const call = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [
    string,
    RequestInit | undefined,
  ]
  return [String(call[0]), call[1]]
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('request — Non-OK-Responses', () => {
  it.each([400, 401, 403, 404, 409, 422, 429, 500])(
    'reicht Status %i als ApiError.status durch',
    async (status) => {
      stubFetch(() => new Response('', { status }))
      await expect(createApi('tok', WS).listPersonas()).rejects.toMatchObject({
        name: 'ApiError',
        status,
        message: `Who2Be-API-Fehler (${status}).`,
      })
    },
  )

  it('nutzt die Fallback-Message bei ganz fehlendem Content-Type-Header', async () => {
    // Body-lose Response traegt keinen impliziten text/plain-Header —
    // `headers.get('content-type')` ist null → `?? ''`-Fallback.
    stubFetch(() => new Response(null, { status: 500 }))
    await expect(createApi('tok', WS).listResourceTags()).rejects.toMatchObject({
      status: 500,
      message: 'Who2Be-API-Fehler (500).',
      body: null,
    })
  })

  it('nutzt die Fallback-Message bei Text-Body ohne JSON-Content-Type', async () => {
    stubFetch(() => new Response('kaputt', { status: 500 }))
    const error = await createApi('tok', WS)
      .getPersona('p1')
      .then(
        () => null,
        (e: unknown) => e as ApiError,
      )
    expect(error).toBeInstanceOf(ApiError)
    expect(error?.message).toBe('Who2Be-API-Fehler (500).')
    expect(error?.body).toBeNull()
  })

  it('ignoriert Plain-Text-Bodies (kein JSON-Parse-Versuch)', async () => {
    stubFetch(
      () =>
        new Response('<html>Bad Gateway</html>', {
          status: 502,
          headers: { 'content-type': 'text/html' },
        }),
    )
    await expect(createApi('tok', WS).listAgents()).rejects.toMatchObject({
      status: 502,
      message: 'Who2Be-API-Fehler (502).',
      body: null,
    })
  })

  it('liest die detail-Message aus einem problem+json-Body', async () => {
    stubFetch(() => problemResponse({ detail: 'Version ist nicht im Status draft.' }, 409))
    await expect(
      createApi('tok', WS).transitionPersonaVersion('p1', 3, 'active'),
    ).rejects.toMatchObject({
      status: 409,
      message: 'Version ist nicht im Status draft.',
    })
  })

  it('liest die detail-Message aus einem application/json-Body', async () => {
    stubFetch(() => jsonResponse({ detail: 'Nicht autorisiert.' }, 401))
    await expect(createApi('tok', WS).listResources()).rejects.toMatchObject({
      status: 401,
      message: 'Nicht autorisiert.',
    })
  })

  it('faellt bei leerem detail-String auf die generische Message zurueck', async () => {
    stubFetch(() => jsonResponse({ detail: '' }, 403))
    await expect(createApi('tok', WS).listMembers()).rejects.toMatchObject({
      status: 403,
      message: 'Who2Be-API-Fehler (403).',
    })
  })

  it('behaelt bei Objekt-detail (DeleteBlocked-409) den Body am ApiError', async () => {
    const detail = {
      message: 'Persona wird von Agenten verwendet.',
      blocked_by: { agents: [{ agent_id: 'a1', agent_name: 'Builder' }] },
    }
    stubFetch(() => problemResponse({ detail }, 409))
    const error = await createApi('tok', WS)
      .deletePersona('p1')
      .then(
        () => null,
        (e: unknown) => e as ApiError,
      )
    expect(error?.status).toBe(409)
    // Objekt-detail ist kein String → generische Message, aber der Roh-Body
    // bleibt fuer `extractDeleteBlockers` & Co. erhalten.
    expect(error?.message).toBe('Who2Be-API-Fehler (409).')
    expect(error?.body).toEqual({ detail })
  })

  it('faengt invalides JSON trotz JSON-Content-Type ab (catch-Pfad)', async () => {
    stubFetch(
      () =>
        new Response('{nicht: json', {
          status: 422,
          headers: { 'content-type': 'application/json' },
        }),
    )
    await expect(createApi('tok', WS).createPersona({} as never)).rejects.toMatchObject({
      status: 422,
      message: 'Who2Be-API-Fehler (422).',
      body: null,
    })
  })
})

describe('request — Netzwerkfehler', () => {
  it('mappt einen fetch-Reject auf ApiError(0) und loggt die GET-Ursache', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(createApi('tok', WS).listPlaybooks()).rejects.toMatchObject({
      status: 0,
      message: 'Who2Be-API nicht erreichbar.',
    })
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('GET'),
      expect.any(TypeError),
    )
  })

  it('loggt bei Mutationen die HTTP-Methode aus init', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(createApi('tok', WS).createAgent({} as never)).rejects.toBeInstanceOf(
      ApiError,
    )
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('POST'),
      expect.any(TypeError),
    )
  })

  it('mappt Netzwerkfehler auch im Text-Pfad (Markdown-Export) auf ApiError(0)', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(createApi('tok', WS).exportPersona('p1', 'markdown')).rejects.toMatchObject({
      status: 0,
      message: 'Who2Be-API nicht erreichbar.',
    })
  })
})

describe('request — 204 / leere Bodies', () => {
  it('gibt bei 204 undefined zurueck (deleteResource)', async () => {
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }))
    await expect(createApi('tok', WS).deleteResource('r1')).resolves.toBeUndefined()
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/v1/workspaces/${WS}/resources/r1`)
    expect(init?.method).toBe('DELETE')
  })

  it('loescht ein Playbook per DELETE mit 204', async () => {
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }))
    await expect(createApi('tok', WS).deletePlaybook('pb1')).resolves.toBeUndefined()
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/playbooks/pb1`)
    expect(init?.method).toBe('DELETE')
  })

  it('loescht einen Feedback-Eintrag per DELETE mit 204', async () => {
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }))
    await expect(createApi('tok', WS).deleteFeedback('fb1')).resolves.toBeUndefined()
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/feedback/fb1`)
    expect(init?.method).toBe('DELETE')
  })
})

describe('Token- und Header-Handling', () => {
  it('laesst den Authorization-Header bei leerem Token weg', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await fetchMe('')
    const [, init] = lastCall(fetchMock)
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers['Content-Type']).toBe('application/json')
  })

  it('laesst den Authorization-Header auch im Text-Pfad bei leerem Token weg', async () => {
    const fetchMock = stubFetch(() => new Response('# Export', { status: 200 }))
    await createApi('', WS).exportPlaybook('pb1', 'markdown')
    const [, init] = lastCall(fetchMock)
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    // Text-Requests schicken keinen JSON-Content-Type mit.
    expect(headers['Content-Type']).toBeUndefined()
  })

  it('schickt die aktive UI-Sprache als Accept-Language', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await createApi('tok', WS).listPersonas()
    const [, init] = lastCall(fetchMock)
    const headers = init?.headers as Record<string, string>
    expect(headers['Accept-Language']).toBe('de')
  })

  it('faellt ohne resolvedLanguage auf language bzw. DEFAULT_LOCALE zurueck', async () => {
    // i18n-Singleton: `resolvedLanguage`/`language` sind plain Properties der
    // Instanz — fuer die ??-Ketten temporaer wegnehmen und danach restaurieren.
    const mutable = i18n as { resolvedLanguage?: string; language: string }
    const originalResolved = mutable.resolvedLanguage
    const originalLanguage = mutable.language
    try {
      mutable.resolvedLanguage = undefined
      mutable.language = 'en'
      const fetchMock = stubFetch(() => jsonResponse([]))
      await createApi('tok', WS).listPersonas()
      let [, init] = lastCall(fetchMock)
      expect((init?.headers as Record<string, string>)['Accept-Language']).toBe('en')

      mutable.language = undefined as unknown as string
      // JSON- und Text-Pfad haben je eine eigene ??-Kette — beide pruefen.
      await createApi('tok', WS).listPersonas()
      ;[, init] = lastCall(fetchMock)
      expect((init?.headers as Record<string, string>)['Accept-Language']).toBe(DEFAULT_LOCALE)
      await createApi('tok', WS).exportResource('r1', 'markdown').catch(() => undefined)
      ;[, init] = lastCall(fetchMock)
      expect((init?.headers as Record<string, string>)['Accept-Language']).toBe(DEFAULT_LOCALE)
    } finally {
      mutable.resolvedLanguage = originalResolved
      mutable.language = originalLanguage
    }
  })
})

describe('Einzel-Element-Export', () => {
  it('liefert den JSON-Export als geparstes Objekt', async () => {
    const dump = { id: 'p1', versions: [{ version: 1 }] }
    const fetchMock = stubFetch(() => jsonResponse(dump))
    const result = await createApi('tok', WS).exportPersona('p1', 'json')
    expect(result).toEqual(dump)
    const [url] = lastCall(fetchMock)
    expect(url).toContain(`/personas/p1/export?format=json`)
  })

  it('liefert den Markdown-Export als Roh-Text', async () => {
    const fetchMock = stubFetch(
      () =>
        new Response('---\ntitle: X\n---\n# Body', {
          status: 200,
          headers: { 'content-type': 'text/markdown' },
        }),
    )
    const result = await createApi('tok', WS).exportResource('r1', 'markdown')
    expect(result).toBe('---\ntitle: X\n---\n# Body')
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/resources/r1/export?format=markdown`)
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer tok')
  })

  it('reicht problem+json-Fehler auch im Text-Pfad als ApiError durch', async () => {
    stubFetch(() => problemResponse({ detail: 'Keine aktive Version.' }, 404))
    await expect(createApi('tok', WS).exportPlaybook('pb1', 'markdown')).rejects.toMatchObject({
      status: 404,
      message: 'Keine aktive Version.',
    })
  })
})

describe('Query-Param-Bau', () => {
  it('listPlaybooks ohne Filter haengt kein "?" an', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await createApi('tok', WS).listPlaybooks()
    const [url] = lastCall(fetchMock)
    expect(url.endsWith(`/v1/workspaces/${WS}/playbooks`)).toBe(true)
  })

  it('listPlaybooks mit leeren Filter-Strings haengt kein "?" an', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await createApi('tok', WS).listPlaybooks({ tag: '', trigger: '' })
    const [url] = lastCall(fetchMock)
    expect(url).not.toContain('?')
  })

  it('listPlaybooks kombiniert tag- und trigger-Filter', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await createApi('tok', WS).listPlaybooks({ tag: 'onboarding', trigger: 'pr opened' })
    const [url] = lastCall(fetchMock)
    expect(url).toContain('tag=onboarding')
    expect(url).toContain('trigger=pr+opened')
  })

  it('listPlaybooks mit nur trigger setzt genau diesen Parameter', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await createApi('tok', WS).listPlaybooks({ trigger: 'deploy' })
    const [url] = lastCall(fetchMock)
    expect(url).toContain('?trigger=deploy')
    expect(url).not.toContain('tag=')
  })

  it('listTokens haengt agent_id nur bei gesetztem Filter an', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    const api = createApi('tok', WS)
    await api.listTokens()
    expect(lastCall(fetchMock)[0].endsWith('/tokens')).toBe(true)
    await api.listTokens({ agentId: 'a1' })
    expect(lastCall(fetchMock)[0]).toContain('/tokens?agent_id=a1')
  })

  it('getDashboard paginiert erst ab Seite 2', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    const api = createApi('tok', WS)
    await api.getDashboard()
    expect(lastCall(fetchMock)[0].endsWith('/dashboard')).toBe(true)
    await api.getDashboard(1)
    expect(lastCall(fetchMock)[0].endsWith('/dashboard')).toBe(true)
    await api.getDashboard(3)
    expect(lastCall(fetchMock)[0]).toContain('/dashboard?page=3')
  })

  it('renderAgentPrompt haengt format nur bei Angabe an', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    const api = createApi('tok', WS)
    await api.renderAgentPrompt('a1')
    expect(lastCall(fetchMock)[0].endsWith('/agents/a1/render')).toBe(true)
    await api.renderAgentPrompt('a1', 'markdown')
    expect(lastCall(fetchMock)[0]).toContain('/agents/a1/render?format=markdown')
  })

  it('previewPlaceholder traegt persona_id nur bei Angabe', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    const api = createApi('tok', WS)
    await api.previewPlaceholder({ kind: 'playbook', target_id: 't1' })
    let [url] = lastCall(fetchMock)
    expect(url).toContain('/placeholders/preview?kind=playbook&target_id=t1')
    expect(url).not.toContain('persona_id')
    await api.previewPlaceholder({ kind: 'persona-field', target_id: 't1', persona_id: 'p9' })
    ;[url] = lastCall(fetchMock)
    expect(url).toContain('persona_id=p9')
  })

  it('diff-Endpoints defaulten auf against=active und encoden Custom-Werte', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    const api = createApi('tok', WS)
    await api.diffPersonaVersion('p1', 2)
    expect(lastCall(fetchMock)[0]).toContain('/personas/p1/versions/2/diff?against=active')
    await api.diffPlaybookVersion('pb1', 4, '3')
    expect(lastCall(fetchMock)[0]).toContain('/playbooks/pb1/versions/4/diff?against=3')
    await api.diffResourceVersion('r1', 5, 'active')
    expect(lastCall(fetchMock)[0]).toContain('/resources/r1/versions/5/diff?against=active')
    await api.diffSystemPromptTemplateVersion('sp1', 6, 'a b')
    expect(lastCall(fetchMock)[0]).toContain(
      '/system-prompts/sp1/versions/6/diff?against=a%20b',
    )
  })

  it('listResourcesByTag URL-encoded den Tag', async () => {
    const fetchMock = stubFetch(() => jsonResponse([]))
    await createApi('tok', WS).listResourcesByTag('küchen tipps')
    const [url] = lastCall(fetchMock)
    expect(url).toContain(`/resources?tag=k%C3%BCchen+tipps`)
  })
})

describe('bislang untestierte Methoden', () => {
  it('renameToken schickt PATCH mit dem neuen Namen', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    await createApi('tok', WS).renameToken('t1', { name: 'Neu' })
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/tokens/t1`)
    expect(init?.method).toBe('PATCH')
    expect(JSON.parse(String(init?.body))).toEqual({ name: 'Neu' })
  })

  it('rotateToken schickt POST auf /rotate', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    await createApi('tok', WS).rotateToken('t1')
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/tokens/t1/rotate`)
    expect(init?.method).toBe('POST')
  })

  it('submitSystemFeedback schickt POST auf /system-feedback', async () => {
    const fetchMock = stubFetch(() => new Response(null, { status: 204 }))
    await createApi('tok', WS).submitSystemFeedback({ note: 'MCP down' } as never)
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain(`/system-feedback`)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ note: 'MCP down' })
  })

  it('copyAgent schickt ohne Input ein leeres JSON-Objekt', async () => {
    const fetchMock = stubFetch(() => jsonResponse({}))
    const api = createApi('tok', WS)
    await api.copyAgent('a1')
    expect(String(lastCall(fetchMock)[1]?.body)).toBe('{}')
    await api.copyAgent('a1', { name: 'Kopie' } as never)
    expect(JSON.parse(String(lastCall(fetchMock)[1]?.body))).toEqual({ name: 'Kopie' })
  })

  it('oauthConsent schickt POST auf /oauth/consent mit dem Consent-Payload', async () => {
    const fetchMock = stubFetch(() => jsonResponse({ redirect: 'https://claude.ai/cb' }))
    const result = await oauthConsent('tok', {
      request: 'blob.sig',
      agent_id: 'a1',
      approve: true,
    })
    expect(result.redirect).toBe('https://claude.ai/cb')
    const [url, init] = lastCall(fetchMock)
    expect(url).toContain('/oauth/consent')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      request: 'blob.sig',
      agent_id: 'a1',
      approve: true,
    })
  })

  it('acceptInvitation reicht Backend-Fehler (410 abgelaufen) durch', async () => {
    stubFetch(() => problemResponse({ detail: 'Einladung abgelaufen.' }, 410))
    await expect(acceptInvitation('tok', 'plain-token')).rejects.toMatchObject({
      status: 410,
      message: 'Einladung abgelaufen.',
    })
  })
})
