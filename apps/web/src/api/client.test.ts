import i18n from 'i18next'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { acceptInvitation, ApiError, createApi, fetchMe } from './client'

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

  const errorResponse = (payload: Record<string, unknown>, status = 404) =>
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status,
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

  it('uebersetzt agent_disabled (W1) und faellt bei unbekanntem Grund auf detail zurueck', async () => {
    // Beide Haelften der Zusage in einem Fall: der Grund dieser Welle traegt
    // englischen Text, ein Grund ohne Locale-Key den deutschen Servertext.
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse({ detail: 'Agent ist deaktiviert.', reason: 'agent_disabled' }, 409),
    )
    await expect(createApi('tok', WS).renderAgentPrompt('x')).rejects.toMatchObject({
      status: 409,
      message: 'Agent is disabled.',
    })

    vi.stubGlobal(
      'fetch',
      errorResponse({ detail: 'Agent ist deaktiviert.', reason: 'agent_deaktiviert' }, 409),
    )
    await expect(createApi('tok', WS).renderAgentPrompt('x')).rejects.toMatchObject({
      status: 409,
      message: 'Agent ist deaktiviert.',
    })

    await i18n.changeLanguage('de')
  })

  it('uebersetzt playbook_not_found (W5) in die UI-Sprache', async () => {
    // Der Backlink-404 ist der Fall, der die Welle traegt: derselbe deutsche
    // Servertext steht heute in mehreren Services, der `reason` trennt ihn
    // sauber vom Resource-Pendant.
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse({ detail: 'Playbook nicht gefunden.', reason: 'playbook_not_found' }),
    )
    await expect(createApi('tok', WS).getPlaybookUsages('x')).rejects.toMatchObject({
      status: 404,
      message: 'Playbook not found.',
    })

    await i18n.changeLanguage('de')
  })

  it('uebersetzt invitation_no_longer_valid (W3) in die UI-Sprache', async () => {
    // Onboarding-Pfad: der abgelaufene Einladungslink ist oft die erste
    // Server-Meldung, die ein neuer Nutzer ueberhaupt sieht — sie darf nicht
    // deutsch in einer englischen Oberflaeche stehen.
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse(
        { detail: 'Einladung ist nicht mehr gueltig.', reason: 'invitation_no_longer_valid' },
        410,
      ),
    )
    await expect(acceptInvitation('tok', 'abc')).rejects.toMatchObject({
      status: 410,
      message: 'This invitation is no longer valid.',
    })

    await i18n.changeLanguage('de')
  })

  it('uebersetzt persona_not_found und composition_cycle (W2) in die UI-Sprache', async () => {
    // Die beiden Enden der Welle: der haeufigste Editor-404 und der
    // Zyklus-Guard der Kompositionen. Letzterer traegt einen eigenen
    // snake_case-Grund NEBEN dem clientseitigen `errors.cycleRejected` — beide
    // Schreibweisen koexistieren bewusst (Wire-Wert vom Server vs. Meldung,
    // die die Hooks selbst setzen).
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse({ detail: 'Persona nicht gefunden.', reason: 'persona_not_found' }),
    )
    await expect(createApi('tok', WS).getPersona('x')).rejects.toMatchObject({
      status: 404,
      message: 'Persona not found.',
    })

    vi.stubGlobal(
      'fetch',
      errorResponse(
        { detail: 'Verknuepfung wuerde einen Zyklus erzeugen.', reason: 'composition_cycle' },
        409,
      ),
    )
    await expect(createApi('tok', WS).setPlaybookComposes('x', ['y'])).rejects.toMatchObject({
      status: 409,
      message: 'Linking would create a cycle.',
    })

    await i18n.changeLanguage('de')
  })

  it('interpoliert das Limit in entity_quota_exceeded (W3)', async () => {
    // AK 4: die erreichte Grenze kommt als `params` und wird in den
    // uebersetzten Text interpoliert — ein Key fuer jede Grenze.
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse(
        {
          detail: 'Free-Tarif erreicht das Limit von 50 Eintraegen je Workspace. '
            + 'Upgrade auf Pro hebt die Grenze auf — Bestehendes bleibt nutzbar.',
          reason: 'entity_quota_exceeded',
          params: { limit: 50 },
        },
        402,
      ),
    )
    await expect(createApi('tok', WS).listPersonas()).rejects.toMatchObject({
      status: 402,
      message:
        'The free plan is limited to 50 entries per workspace. '
        + 'Upgrading to Pro lifts the limit — existing entries stay usable.',
    })

    await i18n.changeLanguage('de')
  })

  it('uebersetzt invalid_credentials und interpoliert das Rate-Limit (W6)', async () => {
    // Beide Zusagen der letzten Welle in einem Fall: der 401-Sammelgrund
    // (bewusst grobkoernig — ein feinerer waere ein Enumerations-Orakel) und
    // die Grenze als `params`, damit nicht jede konfigurierte Rate ihren
    // eigenen Locale-Key braucht.
    await i18n.changeLanguage('en')
    vi.stubGlobal(
      'fetch',
      errorResponse(
        { detail: 'Ungueltige oder fehlende Anmeldedaten.', reason: 'invalid_credentials' },
        401,
      ),
    )
    await expect(createApi('tok', WS).listPersonas()).rejects.toMatchObject({
      status: 401,
      message: 'Invalid or missing credentials.',
    })

    vi.stubGlobal(
      'fetch',
      errorResponse(
        {
          detail: 'Token-Ratenlimit ueberschritten.',
          reason: 'mcp_rate_limited',
          params: { limit: 30 },
        },
        429,
      ),
    )
    await expect(createApi('tok', WS).listPersonas()).rejects.toMatchObject({
      status: 429,
      message: 'Token rate limit exceeded (30/min).',
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
