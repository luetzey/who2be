import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { EntitlementInfo } from '@/api/types'
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
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...cloudActive, features: ['core'] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ checkout_url: 'https://mollie.test/checkout/abc' }), {
          status: 200,
        }),
      )
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
    const checkoutCall = fetchMock.mock.calls[1]
    expect(String(checkoutCall[0])).toContain('/billing/checkout')
    expect(checkoutCall[1]).toMatchObject({ method: 'POST' })
  })

  it('zeigt einen Fehler, wenn der Checkout fehlschlaegt', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...cloudActive, features: ['core'] }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({}), { status: 500 }))
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
