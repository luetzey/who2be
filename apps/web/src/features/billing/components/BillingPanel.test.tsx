import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { EntitlementInfo } from '@/api/types'
import { renderInRoutes } from '@/test/render'

import { BillingPanel } from './BillingPanel'

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
  usage: { period: '202606', count: 250 },
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
    expect(screen.getByText('29 €/Monat')).toBeInTheDocument()
    // "unbegrenzt" steht sowohl bei "Gueltig bis" (kein Ablauf) als auch beim
    // Entity-Limit — deshalb ueber den zugehoerigen dt-Nachbarn pruefen statt
    // ueber den (zweifach vorkommenden) Text allein.
    expect(screen.getByText('Entity-Limit je Workspace').nextElementSibling).toHaveTextContent(
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
