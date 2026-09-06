import i18n from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, createApi, fetchMe } from './client'

const WS = 'ws-123'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createApi', () => {
  it('sendet den Bearer-Token im Authorization-Header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await createApi('geheim', WS).listPersonas()

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(String(url)).toContain(`/v1/workspaces/${WS}/personas`)
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer geheim')
  })

  it('haengt gesetzte Filter als Query-Parameter an', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await createApi('tok', WS).listPlaybooks({ tag: 'onboarding' })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain(`/v1/workspaces/${WS}/playbooks`)
    expect(url).toContain('tag=onboarding')
  })

  it('wirft ApiError bei einem Fehlerstatus', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 404 })))
    await expect(createApi('tok', WS).getPersona('x')).rejects.toBeInstanceOf(ApiError)
  })

  it('reicht das Backend-detail als ApiError-Message durch', async () => {
    const body = JSON.stringify({ detail: 'Persona nicht gefunden.' })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(body, {
          status: 404,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )

    await expect(createApi('tok', WS).getPersona('x')).rejects.toMatchObject({
      status: 404,
      message: 'Persona nicht gefunden.',
    })
  })

  // --- Server-Fehlercodes (ADR-0051, #436) ---------------------------------

  const errorResponse = (payload: Record<string, unknown>) =>
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      }),
    )

  it('zeigt bei UI-Sprache EN den englischen Text zu einem bekannten reason', async () => {
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse({ detail: 'Agent nicht gefunden.', reason: 'agent_not_found' }),
    )

    await expect(createApi('tok', WS).getAgent('x')).rejects.toMatchObject({
      status: 404,
      message: 'Agent not found.',
    })

    await i18n.changeLanguage('de')
  })

  it('faellt bei unbekanntem reason auf das Server-detail zurueck', async () => {
    // Das ist die Zusage, die die Wellen-Migration ueberhaupt erlaubt: ein
    // Grund ohne Locale-Key zeigt den Servertext, nie einen rohen Key.
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse({ detail: 'Etwas ganz Neues ging schief.', reason: 'brandneuer_grund' }),
    )

    await expect(createApi('tok', WS).getAgent('x')).rejects.toMatchObject({
      message: 'Etwas ganz Neues ging schief.',
    })

    await i18n.changeLanguage('de')
  })

  it('interpoliert params in die Meldung', async () => {
    vi.stubGlobal(
      'fetch',
      errorResponse({
        detail: 'Datei zu gross (max. {{limit}}).',
        reason: 'noch_kein_key',
        params: { limit: '10 MB' },
      }),
    )

    await expect(createApi('tok', WS).getAgent('x')).rejects.toMatchObject({
      message: 'Datei zu gross (max. 10 MB).',
    })
  })

  it('laesst params den defaultValue nicht ueberschreiben', async () => {
    // Der Server ist vertrauenswuerdig, aber `defaultValue` ist ein
    // i18next-Steuerfeld — es darf nicht aus einem Datenfeld kommen.
    vi.stubGlobal(
      'fetch',
      errorResponse({
        detail: 'Echtes Server-detail.',
        reason: 'noch_kein_key',
        params: { defaultValue: 'gekapert' },
      }),
    )

    await expect(createApi('tok', WS).getAgent('x')).rejects.toMatchObject({
      message: 'Echtes Server-detail.',
    })
  })

  it('wirft ApiError bei einem Netzwerkfehler', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(createApi('tok', WS).listPersonas()).rejects.toBeInstanceOf(ApiError)
  })

  it('widerruft einen Token per DELETE und 204', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await createApi('tok', WS).revokeToken('t1')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain(`/v1/workspaces/${WS}/tokens/t1`)
    expect(init.method).toBe('DELETE')
  })
})

describe('fetchMe', () => {
  it('ruft /v1/me ohne Workspace-Prefix auf', async () => {
    const body = JSON.stringify({
      user_id: 'u1',
      default_workspace_id: 'ws-1',
      organizations: [],
    })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const me = await fetchMe('tok')

    expect(String(fetchMock.mock.calls[0][0])).toContain('/v1/me')
    expect(me.default_workspace_id).toBe('ws-1')
  })
})
