import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { BillingProfile, BillingProfileInput, BillingProfileResponse } from '@/api/client'
import type { EntitlementInfo, Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { BillingPanel, formatBytes } from './BillingPanel'

const originalLocation = window.location

afterEach(() => {
  vi.unstubAllGlobals()
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: originalLocation,
  })
})

function jsonFetch(payload: unknown, status = 200) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status }))
}

const cloudActive: EntitlementInfo = {
  edition: 'cloud',
  status: 'active',
  features: ['core', 'sso'],
  expires_at: null,
  mcp_monthly_quota: 1000,
  mcp_rate_per_min: 30,
  token_quota: 3,
  storage_quota_bytes: 100 * 1024 * 1024,
  workspace_quota: 1,
  usage: { period: '202606', count: 250, storage_bytes: 25 * 1024 * 1024 },
}

function renderPanel() {
  return renderInRoutes(<BillingPanel />, {
    path: '/w/:workspaceId/settings/billing',
    initialEntries: ['/w/ws-1/settings/billing'],
  })
}

describe('BillingPanel', () => {
  it('zeigt Status, Features und MCP-Verbrauch in der Cloud-Edition', async () => {
    vi.stubGlobal('fetch', jsonFetch(cloudActive))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Aktiv')).toBeInTheDocument()
    })
    expect(screen.getByText('250 / 1000')).toBeInTheDocument()
    expect(screen.getByText('core')).toBeInTheDocument()
    expect(screen.getByText('sso')).toBeInTheDocument()
    expect(screen.getByText('30/min')).toBeInTheDocument()
    expect(
      screen.getByRole('progressbar', { name: /MCP-Kontingent/ }),
    ).toBeInTheDocument()
  })

  // --- Workspace-Deckel je Org (Issue #576) ---------------------------------

  it('zeigt den Workspace-Deckel des Tarifs als Zahl', async () => {
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, workspace_quota: 5 }))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Workspaces je Organisation')).toBeInTheDocument()
    })
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('zeigt "unbegrenzt", wenn kein Workspace-Deckel gilt (On-Prem/OSS)', async () => {
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, workspace_quota: null }))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Workspaces je Organisation')).toBeInTheDocument()
    })
    // Die Zeile steht direkt nach ihrem Label — sonst faenden wir das
    // "unbegrenzt" einer anderen Zeile.
    const label = screen.getByText('Workspaces je Organisation')
    expect(label.nextElementSibling).toHaveTextContent('unbegrenzt')
  })

  // --- Speicher-Quota (Issue #536, AK 5) ------------------------------------

  it('zeigt belegten Speicher gegen die Grenze des Tarifs', async () => {
    vi.stubGlobal('fetch', jsonFetch(cloudActive))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Aktiv')).toBeInTheDocument()
    })
    // Binaere Einheiten — 100 MB Free sind 100 * 1024 * 1024 Bytes.
    expect(screen.getByText('25 MB / 100 MB')).toBeInTheDocument()
    const bar = screen.getByRole('progressbar', { name: 'Speicher-Verbrauch' })
    expect(bar).toHaveAttribute('aria-valuenow', String(25 * 1024 * 1024))
    expect(bar).toHaveAttribute('aria-valuemax', String(100 * 1024 * 1024))
  })

  it('zeigt "unbegrenzt", wenn keine Speichergrenze gesetzt ist', async () => {
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, storage_quota_bytes: null }))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Speicher: unbegrenzt')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('progressbar', { name: 'Speicher-Verbrauch' }),
    ).not.toBeInTheDocument()
  })

  it('markiert eine erschoepfte Speichergrenze', async () => {
    vi.stubGlobal(
      'fetch',
      jsonFetch({
        ...cloudActive,
        usage: { ...cloudActive.usage, storage_bytes: 100 * 1024 * 1024 },
      }),
    )
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('100 MB / 100 MB')).toBeInTheDocument()
    })
    expect(screen.getByRole('progressbar', { name: 'Speicher-Verbrauch' })).toHaveClass(
      'bg-destructive',
    )
  })

  it('formatiert Bytes binaer und rundet erst ab zweistelligen Werten', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1024)).toBe('1 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(100 * 1024 * 1024)).toBe('100 MB')
    expect(formatBytes(10 * 1024 * 1024 * 1024)).toBe('10 GB')
  })

  it('rendert nichts in der On-Prem-Edition', async () => {
    vi.stubGlobal(
      'fetch',
      jsonFetch({ ...cloudActive, edition: 'onprem', mcp_monthly_quota: null }),
    )
    renderPanel()

    // Warten, bis der Lade-Indikator verschwindet; danach bleibt das Panel leer.
    await waitFor(() => {
      expect(screen.queryByText('Lädt…')).not.toBeInTheDocument()
    })
    expect(screen.queryByText('Plan & Nutzung')).not.toBeInTheDocument()
  })

  it('markiert ein inaktives Abonnement', async () => {
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, status: 'inactive', features: [] }))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Inaktiv')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Jetzt upgraden' })).toBeInTheDocument()
  })

  it('zeigt "Pro aktiv" und keinen Upgrade-Button beim Pro-Tier', async () => {
    vi.stubGlobal(
      'fetch',
      jsonFetch({
        ...cloudActive,
        mcp_monthly_quota: 100000,
        mcp_rate_per_min: 240,
      }),
    )
    renderPanel()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Pro aktiv' })).toBeDisabled()
    })
    expect(screen.queryByRole('button', { name: 'Jetzt upgraden' })).not.toBeInTheDocument()
    expect(screen.getByText('9,99 €/Monat')).toBeInTheDocument()
    // "unbegrenzt" steht sowohl bei "Gueltig bis" (kein Ablauf) als auch beim
    // Entity-Limit — deshalb ueber den zugehoerigen dt-Nachbarn pruefen statt
    // ueber den (zweifach vorkommenden) Text allein.
    expect(screen.getByText('Entity-Limit je Workspace').nextElementSibling).toHaveTextContent(
      'unbegrenzt',
    )
  })

  it('zeigt die Token-Grenze aus dem Entitlement, nicht aus der TIERS-Liste', async () => {
    // Issue #538: `token_quota` ist ein echtes Backend-Feld (anders als Preis
    // und Entity-Limit, die das Panel aus `TIERS` dupliziert). Deshalb kommt
    // die Zahl hier direkt aus der Response — ein manual_override mit
    // individueller Grenze wird korrekt angezeigt, ohne Tier-Treffer.
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, mcp_monthly_quota: 50000, token_quota: 9 }))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Aktiv')).toBeInTheDocument()
    })
    expect(screen.getByText('API-Tokens je Workspace').nextElementSibling).toHaveTextContent('9')
  })

  it('zeigt "unbegrenzt" bei token_quota=null (On-Prem-Lizenz)', async () => {
    // Der Endpoint liefert die TATSAECHLICH geltende Grenze
    // (`Entitlement.effective_token_quota`), nicht das rohe Feld: in der Cloud
    // faellt ein leeres Feld auf den Tarifwert zurueck. `null` kommt daher nur
    // noch aus einer On-Prem-Lizenz — und heisst dann wirklich unbegrenzt.
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, token_quota: null }))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Aktiv')).toBeInTheDocument()
    })
    expect(screen.getByText('API-Tokens je Workspace').nextElementSibling).toHaveTextContent(
      'unbegrenzt',
    )
  })

  it('erkennt den Pro-Tier ueber das MCP-Kontingent, nicht ueber Feature-Codes', async () => {
    // Die Pro-Zusagen (composite_playbooks/agents/audit_export) sind Metadaten
    // des Entitlements, keine gegateten Codes — die Tier-Erkennung haengt an
    // `mcp_monthly_quota`. Dieser Test belegt das mit genau den Codes, die aus
    // der Verkaufsdarstellung entfernt wurden, im rohen Backend-Feld.
    vi.stubGlobal(
      'fetch',
      jsonFetch({
        ...cloudActive,
        features: ['core', 'composite_playbooks', 'agents', 'audit_export'],
        mcp_monthly_quota: 100000,
        mcp_rate_per_min: 240,
      }),
    )
    renderPanel()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Pro aktiv' })).toBeDisabled()
    })
  })

  it('zeigt keinen Upgrade-CTA bei einem manual_override-Entitlement mit individueller Quota', async () => {
    // manual_override (docs/licensing/plans.md, POST .../billing/override) kann
    // eine Quota jenseits der beiden TIERS-Werte setzen — hier 50.000, weder
    // Free (1.000) noch Pro (100.000). "Ist bezahlt?" muss trotzdem ueber die
    // Free-Quota-Schwelle erkennen, dass die Org freigeschaltet ist, auch wenn
    // der genaue Tarif-Name unbekannt bleibt.
    vi.stubGlobal(
      'fetch',
      jsonFetch({
        ...cloudActive,
        mcp_monthly_quota: 50000,
        mcp_rate_per_min: 240,
      }),
    )
    renderPanel()

    await waitFor(() => {
      expect(screen.getByText('Aktiv')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: 'Jetzt upgraden' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'unbekannt aktiv' })).toBeDisabled()
  })

  it('zeigt nichts, wenn das Entitlement nicht gefunden wird (404)', async () => {
    vi.stubGlobal('fetch', jsonFetch({}, 404))
    renderPanel()

    await waitFor(() => {
      expect(screen.queryByText('Lädt…')).not.toBeInTheDocument()
    })
    expect(screen.queryByText('Plan & Nutzung')).not.toBeInTheDocument()
    expect(screen.queryByTestId('error-alert')).not.toBeInTheDocument()
  })

  it('zeigt einen Fehler, wenn das Laden des Entitlements fehlschlaegt', async () => {
    vi.stubGlobal('fetch', jsonFetch({}, 500))
    renderPanel()

    await waitFor(() => {
      expect(screen.getByTestId('error-alert')).toBeInTheDocument()
    })
    expect(screen.getByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    expect(screen.queryByText('Plan & Nutzung')).not.toBeInTheDocument()
  })

  // --- Responsive-Audit (Issue #561, design-language.md §4.4) ---------------
  //
  // Zwei Flex-Kinder ohne `min-w-0` sind nicht unter ihre Inhaltsbreite
  // schrumpfbar (`min-width: auto` ist der Default) — auf 320px laeuft die
  // Zeile ueber, statt kontrolliert zu kuerzen. Geprueft wird die Klassen-
  // Zusage, nicht die Pixelbreite: jsdom layoutet nicht. Gleiches Muster wie
  // `components/ui/dialog.test.tsx`.

  async function renderCloudPanel(overrides: Partial<EntitlementInfo> = {}) {
    vi.stubGlobal('fetch', jsonFetch({ ...cloudActive, ...overrides }))
    renderPanel()
    // Auf den Kartentitel warten, nicht auf „Aktiv" — der Status-Text haengt
    // vom Override ab, der Titel nicht.
    await waitFor(() => {
      expect(screen.getByText('Plan & Nutzung')).toBeInTheDocument()
    })
  }

  it('kuerzt das MCP-Kontingent-Label statt die Zeile ueberlaufen zu lassen', async () => {
    await renderCloudPanel()

    const label = screen.getByText('MCP-Reads diesen Monat')
    const value = screen.getByText('250 / 1000')
    expect(label.className.split(/\s+/)).toEqual(expect.arrayContaining(['min-w-0', 'truncate']))
    expect(value.className.split(/\s+/)).toContain('shrink-0')
  })

  it('kuerzt das Speicher-Label statt die Zeile ueberlaufen zu lassen', async () => {
    await renderCloudPanel()

    const label = screen.getByText('Belegter Speicher')
    const value = screen.getByText('25 MB / 100 MB')
    expect(label.className.split(/\s+/)).toEqual(expect.arrayContaining(['min-w-0', 'truncate']))
    expect(value.className.split(/\s+/)).toContain('shrink-0')
  })

  it('haelt das Status-Badge neben dem Kartentitel ungeschrumpft', async () => {
    await renderCloudPanel()

    const title = screen.getByText('Plan & Nutzung')
    const badge = screen.getByText('Aktiv')
    expect(title.className.split(/\s+/)).toEqual(expect.arrayContaining(['min-w-0', 'truncate']))
    expect(badge.className.split(/\s+/)).toContain('shrink-0')
  })

  it('bindet die zweispaltige Plan-Liste an einen Breakpoint (mobile-first)', async () => {
    await renderCloudPanel()

    const list = screen.getByText('Plan').closest('dl')
    expect(list).not.toBeNull()
    const classes = list!.className.split(/\s+/)
    expect(classes).toContain('grid-cols-1')
    expect(classes).toContain('sm:grid-cols-2')
    // Keine nackte Mehrspaltigkeit ohne Prefix (§4.4 „Prefix ist Pflicht").
    expect(classes).not.toContain('grid-cols-2')
  })

  it('haelt den CTA auf dem 40px-Hit-Target (§11 A11y-Minimum)', async () => {
    await renderCloudPanel({ status: 'inactive', features: [] })

    // `size="default"` = `h-10` = 40px; eine Verdichtung auf `size="sm"`
    // (`h-9` = 36px) wuerde das A11y-Minimum unterhalb `md` unterschreiten.
    const cta = screen.getByRole('button', { name: 'Jetzt upgraden' })
    expect(cta.className.split(/\s+/)).toContain('h-10')
  })

  it('startet den Mollie-Checkout beim Upgrade-Klick', async () => {
    // URL-basiert: die Glocke in der Kopfleiste (Navigation W1) fragt nebenher
    // `/inbox/counts` ab und darf die Reihenfolge nicht verschieben.
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/inbox/counts')) {
        return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
      }
      if (String(url).includes('/billing/checkout')) {
        return Promise.resolve(
          new Response(JSON.stringify({ checkout_url: 'https://mollie.test/checkout/abc' }), {
            status: 200,
          }),
        )
      }
      return Promise.resolve(
        new Response(JSON.stringify({ ...cloudActive, features: ['core'] }), { status: 200 }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    const hrefSpy = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        set href(value: string) {
          hrefSpy(value)
        },
      },
    })

    renderPanel()
    const button = await screen.findByRole('button', { name: 'Jetzt upgraden' })
    fireEvent.click(button)

    await waitFor(() => {
      expect(hrefSpy).toHaveBeenCalledWith('https://mollie.test/checkout/abc')
    })
    const checkoutCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes('/billing/checkout'),
    )!
    expect(String(checkoutCall[0])).toContain('/billing/checkout')
    expect(checkoutCall[1]).toMatchObject({ method: 'POST' })
  })

  it('zeigt einen Fehler, wenn der Checkout fehlschlaegt', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes('/inbox/counts')) {
        return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
      }
      if (String(url).includes('/billing/checkout')) {
        return Promise.resolve(new Response(JSON.stringify({}), { status: 500 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ ...cloudActive, features: ['core'] }), { status: 200 }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    renderPanel()
    const button = await screen.findByRole('button', { name: 'Jetzt upgraden' })
    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByTestId('error-alert')).toBeInTheDocument()
    })
    expect(screen.getByText('Who2Be-API-Fehler (500).')).toBeInTheDocument()
    // Nach dem Fehler ist der Button wieder aktiv (kein Redirect erfolgt).
    expect(screen.getByRole('button', { name: 'Jetzt upgraden' })).not.toBeDisabled()
  })
})

// --- Rechnungsdaten (ADR-0061 R1) --------------------------------------------
// Platzhalter-Daten, keine echten Adressen oder USt-IdNr. (oeffentliches Repo).

const adminMe: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'org-1',
      name: 'Beispiel',
      slug: 'beispiel',
      kind: 'company',
      workspaces: [{ id: 'ws-1', name: 'W', slug: 'w', role: 'admin' }],
    },
  ],
}

const savedProfile: BillingProfile = {
  customer_type: 'business',
  given_name: null,
  family_name: null,
  company_name: 'Beispiel GmbH',
  street: 'Musterstrasse 1',
  postal_code: '1010',
  city: 'Musterstadt',
  country: 'AT',
  vat_id: 'ATU00000000',
  vat_status: 'unchecked',
  vat_checked_at: null,
  updated_at: '2026-10-22T10:00:00Z',
}

const COUNTRIES = ['AT', 'CH', 'DE', 'FR', 'GR', 'US']
const EU = ['AT', 'DE', 'FR', 'GR']

function profileResponse(profile: BillingProfile | null): BillingProfileResponse {
  return { profile, countries: COUNTRIES, eu_countries: EU }
}

function billingFetch(options: {
  profile: BillingProfile | null
  onPut?: (body: BillingProfileInput) => Response | Promise<Response>
  onCheckout?: () => Response
}) {
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/inbox/counts')) {
      return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
    }
    if (u.includes('/billing/checkout') && options.onCheckout) {
      return Promise.resolve(options.onCheckout())
    }
    if (u.includes('/billing/profile')) {
      if (init?.method === 'PUT' && options.onPut) {
        return Promise.resolve(options.onPut(JSON.parse(String(init.body)) as BillingProfileInput))
      }
      return Promise.resolve(new Response(JSON.stringify(profileResponse(options.profile))))
    }
    return Promise.resolve(new Response(JSON.stringify({ ...cloudActive, features: ['core'] })))
  })
}

function renderAdminPanel() {
  return renderInRoutes(<BillingPanel />, {
    path: '/w/:workspaceId/settings/billing',
    initialEntries: ['/w/ws-1/settings/billing'],
    me: adminMe,
  })
}

function profileCalls(fetchMock: ReturnType<typeof vi.fn>, method: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      String(url).includes('/billing/profile') && ((init as RequestInit | undefined)?.method ?? 'GET') === method,
  )
}

describe('BillingPanel – Rechnungsdaten', () => {
  it('laedt fuer Nicht-Admins keine Rechnungsdaten und sperrt den Upgrade nicht', async () => {
    const fetchMock = billingFetch({ profile: null })
    vi.stubGlobal('fetch', fetchMock)
    renderPanel()

    const button = await screen.findByRole('button', { name: 'Jetzt upgraden' })
    expect(button).not.toBeDisabled()
    expect(screen.queryByRole('form', { name: 'Rechnungsdaten' })).not.toBeInTheDocument()
    expect(profileCalls(fetchMock, 'GET')).toHaveLength(0)
  })

  it('sperrt den Upgrade, bis Rechnungsdaten gespeichert sind', async () => {
    vi.stubGlobal('fetch', billingFetch({ profile: null }))
    renderAdminPanel()

    expect(await screen.findByRole('form', { name: 'Rechnungsdaten' })).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'Jetzt upgraden' })
    expect(button).toBeDisabled()
    expect(button).toHaveAccessibleDescription(/zuerst die Rechnungsdaten speichern/)
  })

  it('zeigt gespeicherte Daten als Zusammenfassung mit VIES-Status und gibt den Upgrade frei', async () => {
    vi.stubGlobal('fetch', billingFetch({ profile: savedProfile }))
    renderAdminPanel()

    const summary = await screen.findByTestId('billing-details-summary')
    expect(summary).toHaveTextContent('Beispiel GmbH')
    expect(summary).toHaveTextContent('ATU00000000')
    expect(screen.getByText('ungeprüft')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jetzt upgraden' })).not.toBeDisabled()
  })

  it('verlangt je Kundentyp die Pflichtfelder (Client-Validierung)', async () => {
    const fetchMock = billingFetch({ profile: null })
    vi.stubGlobal('fetch', fetchMock)
    renderAdminPanel()

    const form = await screen.findByRole('form', { name: 'Rechnungsdaten' })
    // Firma (Default): Firmenname ist Pflicht, Vor-/Nachname gibt es nicht.
    expect(within(form).getByLabelText('Firmenname')).toBeInTheDocument()
    expect(within(form).queryByLabelText('Vorname')).not.toBeInTheDocument()
    fireEvent.click(within(form).getByRole('button', { name: 'Rechnungsdaten speichern' }))
    expect(await within(form).findAllByText('Pflichtfeld.')).toHaveLength(5)

    // Privat: Vor- und Nachname statt Firmenname, keine USt-IdNr.
    fireEvent.click(within(form).getByRole('radio', { name: 'Privatperson' }))
    expect(within(form).getByLabelText('Vorname')).toBeInTheDocument()
    expect(within(form).queryByLabelText('Firmenname')).not.toBeInTheDocument()
    fireEvent.change(within(form).getByLabelText('Land'), { target: { value: 'AT' } })
    expect(within(form).queryByLabelText('USt-IdNr. (optional)')).not.toBeInTheDocument()

    expect(profileCalls(fetchMock, 'PUT')).toHaveLength(0)
  })

  it('zeigt die USt-IdNr. nur fuer Firmen in der EU und prueft den Laenderpraefix', async () => {
    const fetchMock = billingFetch({ profile: null })
    vi.stubGlobal('fetch', fetchMock)
    renderAdminPanel()

    const form = await screen.findByRole('form', { name: 'Rechnungsdaten' })
    fireEvent.change(within(form).getByLabelText('Land'), { target: { value: 'CH' } })
    expect(within(form).queryByLabelText('USt-IdNr. (optional)')).not.toBeInTheDocument()

    fireEvent.change(within(form).getByLabelText('Land'), { target: { value: 'GR' } })
    fireEvent.change(within(form).getByLabelText('Firmenname'), { target: { value: 'Beispiel AE' } })
    fireEvent.change(within(form).getByLabelText('Straße und Hausnummer'), { target: { value: 'Odos 1' } })
    fireEvent.change(within(form).getByLabelText('PLZ'), { target: { value: '10000' } })
    fireEvent.change(within(form).getByLabelText('Ort'), { target: { value: 'Musterstadt' } })
    fireEvent.change(within(form).getByLabelText('USt-IdNr. (optional)'), {
      target: { value: 'GR000000000' },
    })
    fireEvent.click(within(form).getByRole('button', { name: 'Rechnungsdaten speichern' }))

    expect(await within(form).findByText(/mit EL beginnen/)).toBeInTheDocument()
    expect(profileCalls(fetchMock, 'PUT')).toHaveLength(0)
  })

  it('speichert normalisiert, zeigt den Server-Stand und schaltet den Upgrade frei', async () => {
    const puts: BillingProfileInput[] = []
    let resolvePut: (r: Response) => void = () => {}
    const fetchMock = billingFetch({
      profile: null,
      onPut: (body) => {
        puts.push(body)
        return new Promise<Response>((resolve) => {
          resolvePut = resolve
        })
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAdminPanel()

    const form = await screen.findByRole('form', { name: 'Rechnungsdaten' })
    fireEvent.change(within(form).getByLabelText('Firmenname'), { target: { value: ' Beispiel GmbH ' } })
    fireEvent.change(within(form).getByLabelText('Straße und Hausnummer'), {
      target: { value: 'Musterstrasse 1' },
    })
    fireEvent.change(within(form).getByLabelText('PLZ'), { target: { value: '1010' } })
    fireEvent.change(within(form).getByLabelText('Ort'), { target: { value: 'Musterstadt' } })
    fireEvent.change(within(form).getByLabelText('Land'), { target: { value: 'AT' } })
    fireEvent.change(within(form).getByLabelText('USt-IdNr. (optional)'), {
      target: { value: 'atu 000.000-00' },
    })
    const submit = within(form).getByRole('button', { name: 'Rechnungsdaten speichern' })
    fireEvent.click(submit)

    // Waehrend des Speicherns gesperrt: kein Doppel-Submit.
    await waitFor(() => expect(within(form).getByRole('button', { name: 'Speichert…' })).toBeDisabled())
    fireEvent.submit(form)
    expect(puts).toHaveLength(1)
    expect(puts[0]).toEqual({
      customer_type: 'business',
      given_name: null,
      family_name: null,
      company_name: 'Beispiel GmbH',
      street: 'Musterstrasse 1',
      postal_code: '1010',
      city: 'Musterstadt',
      country: 'AT',
      vat_id: 'ATU00000000',
    })

    resolvePut(new Response(JSON.stringify(profileResponse(savedProfile))))
    expect(await screen.findByTestId('billing-details-summary')).toHaveTextContent('Beispiel GmbH')
    expect(screen.getByText('ungeprüft')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Jetzt upgraden' })).not.toBeDisabled()
  })

  it('ignoriert eine ausgeblendete USt-IdNr. nach Landwechsel (AT -> CH) und speichert ohne vat_id', async () => {
    const puts: BillingProfileInput[] = []
    const fetchMock = billingFetch({
      profile: null,
      onPut: (body) => {
        puts.push(body)
        return new Response(JSON.stringify(profileResponse({ ...savedProfile, country: 'CH', vat_id: null, vat_status: null })))
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAdminPanel()

    const form = await screen.findByRole('form', { name: 'Rechnungsdaten' })
    fireEvent.change(within(form).getByLabelText('Firmenname'), { target: { value: 'Beispiel AG' } })
    fireEvent.change(within(form).getByLabelText('Straße und Hausnummer'), {
      target: { value: 'Musterstrasse 1' },
    })
    fireEvent.change(within(form).getByLabelText('PLZ'), { target: { value: '8000' } })
    fireEvent.change(within(form).getByLabelText('Ort'), { target: { value: 'Musterstadt' } })
    fireEvent.change(within(form).getByLabelText('Land'), { target: { value: 'AT' } })
    fireEvent.change(within(form).getByLabelText('USt-IdNr. (optional)'), {
      target: { value: 'ATU00000000' },
    })
    // Landwechsel blendet das Feld aus; der Rest-Wert bleibt im Form-State.
    fireEvent.change(within(form).getByLabelText('Land'), { target: { value: 'CH' } })
    expect(within(form).queryByLabelText('USt-IdNr. (optional)')).not.toBeInTheDocument()
    fireEvent.click(within(form).getByRole('button', { name: 'Rechnungsdaten speichern' }))

    await waitFor(() => expect(puts).toHaveLength(1))
    expect(puts[0]).toMatchObject({ customer_type: 'business', country: 'CH', vat_id: null })
    expect(await screen.findByTestId('billing-details-summary')).toHaveTextContent('Beispiel GmbH')
  })

  it('zeigt einen Server-Fehler und behaelt die Eingaben', async () => {
    vi.stubGlobal(
      'fetch',
      billingFetch({
        profile: savedProfile,
        onPut: () => new Response(JSON.stringify({ detail: 'nope' }), { status: 422 }),
      }),
    )
    renderAdminPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
    const form = screen.getByRole('form', { name: 'Rechnungsdaten' })
    expect(within(form).getByLabelText('Firmenname')).toHaveValue('Beispiel GmbH')
    fireEvent.change(within(form).getByLabelText('Ort'), { target: { value: 'Andere Stadt' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Rechnungsdaten speichern' }))

    expect(await within(form).findByTestId('error-alert')).toBeInTheDocument()
    expect(within(form).getByLabelText('Ort')).toHaveValue('Andere Stadt')
  })

  it('hat im Formular und in der Zusammenfassung keine axe-Verstoesse', async () => {
    vi.stubGlobal('fetch', billingFetch({ profile: null }))
    const { unmount } = renderAdminPanel()
    const form = await screen.findByRole('form', { name: 'Rechnungsdaten' })
    fireEvent.click(within(form).getByRole('button', { name: 'Rechnungsdaten speichern' }))
    await within(form).findAllByText('Pflichtfeld.')
    expect(await axe(document.body)).toHaveNoViolations()
    unmount()

    vi.stubGlobal('fetch', billingFetch({ profile: savedProfile }))
    renderAdminPanel()
    await screen.findByTestId('billing-details-summary')
    expect(await axe(document.body)).toHaveNoViolations()
  })

  // --- 409 vom Checkout: Rechnungsdaten fehlen serverseitig (R2c) ----------

  function conflictResponse() {
    return new Response(
      JSON.stringify({ detail: 'Rechnungsdaten fehlen. Bitte zuerst die Rechnungsdaten speichern.' }),
      { status: 409, headers: { 'content-type': 'application/json' } },
    )
  }

  it('zeigt bei 409 eine eigene Meldung mit Sprung zu den Rechnungsdaten', async () => {
    // Der Client haelt einen veralteten Stand (Profil vorhanden), der Server nicht.
    vi.stubGlobal('fetch', billingFetch({ profile: savedProfile, onCheckout: conflictResponse }))
    renderAdminPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Jetzt upgraden' }))

    const alert = await screen.findByTestId('checkout-details-missing')
    expect(alert).toHaveTextContent('Rechnungsdaten fehlen')
    expect(alert).toHaveTextContent('Für das Upgrade brauchen wir deine Rechnungsdaten')
    // Die generische Fehlermeldung erscheint nicht zusaetzlich.
    expect(screen.queryByTestId('error-alert')).not.toBeInTheDocument()

    fireEvent.click(within(alert).getByRole('button', { name: 'Zu den Rechnungsdaten' }))
    const card = screen.getByTestId('billing-details-summary').closest('#billing-details')
    expect(card).not.toBeNull()
    expect(card).toHaveFocus()
    // Nach dem Fehler ist der Knopf wieder bedienbar.
    expect(screen.getByRole('button', { name: 'Jetzt upgraden' })).not.toBeDisabled()
  })

  it('zeigt andere Checkout-Fehler weiter als allgemeine Fehlermeldung', async () => {
    vi.stubGlobal(
      'fetch',
      billingFetch({
        profile: savedProfile,
        onCheckout: () =>
          new Response(JSON.stringify({ detail: 'Rechnungsstellung nicht konfiguriert.' }), {
            status: 503,
            headers: { 'content-type': 'application/json' },
          }),
      }),
    )
    renderAdminPanel()

    fireEvent.click(await screen.findByRole('button', { name: 'Jetzt upgraden' }))

    expect(await screen.findByTestId('error-alert')).toHaveTextContent(
      'Rechnungsstellung nicht konfiguriert.',
    )
    expect(screen.queryByTestId('checkout-details-missing')).not.toBeInTheDocument()
  })

  it('hat mit der 409-Meldung keine axe-Verstoesse', async () => {
    vi.stubGlobal('fetch', billingFetch({ profile: savedProfile, onCheckout: conflictResponse }))
    renderAdminPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'Jetzt upgraden' }))
    await screen.findByTestId('checkout-details-missing')
    expect(await axe(document.body)).toHaveNoViolations()
  })
})
