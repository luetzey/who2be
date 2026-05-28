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
