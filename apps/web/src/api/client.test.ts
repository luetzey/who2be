import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, createApi } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createApi', () => {
  it('sendet den Bearer-Token im Authorization-Header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await createApi('geheim').listPersonas()

    const init = fetchMock.mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer geheim')
  })

  it('haengt gesetzte Filter als Query-Parameter an', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await createApi('tok').listPlaybooks({ tag: 'onboarding' })

    expect(String(fetchMock.mock.calls[0][0])).toContain('tag=onboarding')
  })

  it('wirft ApiError bei einem Fehlerstatus', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 404 })))
    await expect(createApi('tok').getPersona('x')).rejects.toBeInstanceOf(ApiError)
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

    await expect(createApi('tok').getPersona('x')).rejects.toMatchObject({
      status: 404,
      message: 'Persona nicht gefunden.',
    })
  })

  it('wirft ApiError bei einem Netzwerkfehler', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(createApi('tok').listPersonas()).rejects.toBeInstanceOf(ApiError)
  })

  it('widerruft einen Token per DELETE und 204', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await createApi('tok').revokeToken('t1')

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/v1/tokens/t1')
    expect(init.method).toBe('DELETE')
  })
})
