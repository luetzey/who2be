import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryAutoPolicyRead, MemoryGuardMode } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { notify } from '@/lib/feedback'

import de from '@/i18n/locales/de.json'
import en from '@/i18n/locales/en.json'

import { AUTO_APPROVAL_LIMIT_KEYS } from './AutoApprovalLimitsDialog'
import { MemoryApprovalSection } from './MemoryApprovalSection'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({
  useIsMobile: () => viewport.mobile,
  useMediaQuery: () => viewport.mobile,
}))

// Radix Dialog/Tooltip nutzen PointerCapture-APIs, die jsdom nicht kennt.
beforeAll(() => {
  for (const method of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ]) {
    Object.defineProperty(window.HTMLElement.prototype, method, {
      value: () => undefined,
      configurable: true,
    })
  }
})

const session = { access_token: 'jwt' } as unknown as Session

function buildMe(): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role: 'admin' }],
      },
    ],
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

const SWITCHABLE = [{ row: 'user_fact', origin: 'user_stated' }] as const

function policy(enabled: boolean): MemoryAutoPolicyRead {
  return {
    enabled_cells: enabled ? [...SWITCHABLE] : [],
    switchable_cells: [...SWITCHABLE],
  }
}

interface StubOptions {
  initial?: MemoryAutoPolicyRead
  guardMode?: MemoryGuardMode
  policyStatus?: number
  putStatus?: number
}

function stubApi({ initial = policy(false), guardMode = 'standard', policyStatus = 200, putStatus = 200 }: StubOptions = {}) {
  const puts: unknown[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/memory-auto-policy')) {
      if ((init?.method ?? 'GET') === 'PUT') {
        const body = JSON.parse(init?.body as string) as { enabled_cells: unknown[] }
        puts.push(body)
        if (putStatus !== 200) {
          return jsonResponse({ detail: 'kaputt' }, putStatus)
        }
        return jsonResponse({ enabled_cells: body.enabled_cells, switchable_cells: [...SWITCHABLE] })
      }
      if (policyStatus !== 200) {
        return jsonResponse({ detail: 'verboten' }, policyStatus)
      }
      return jsonResponse(initial)
    }
    if (url.includes('/memory-guard')) {
      return jsonResponse({ mode: guardMode, allow_phrases: [], block_phrases: [] })
    }
    return jsonResponse([])
  })
  vi.stubGlobal('fetch', fetchMock)
  return { puts, fetchMock }
}

function renderSection() {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me: buildMe(),
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn().mockResolvedValue(undefined),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/settings/workspace']}>
          <Routes>
            <Route path="/w/:workspaceId/settings/workspace" element={<MemoryApprovalSection />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  viewport.mobile = false
})

describe('MemoryApprovalSection (Lernschleife C6, ADR-0053 4.2/4.3)', () => {
  it('macht nur die vom Server genannte Zelle schaltbar; alle anderen stehen als „Immer prüfen“', async () => {
    stubApi()
    renderSection()
    const toggle = await screen.findByRole('switch', { name: 'Nutzerfakt Von dir gesagt' })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    // Genau ein Bedienelement in der ganzen Matrix.
    expect(screen.getAllByRole('switch')).toHaveLength(1)
    // 4 Zeilen x 3 Herkünfte = 12 Zellen, davon 11 gesperrt.
    expect(document.querySelectorAll('[data-locked-cell]')).toHaveLength(11)
    const instructionRow = screen.getByRole('rowheader', { name: 'Nutzerfakt mit Anweisung' }).closest('tr')!
    expect(within(instructionRow).getAllByText('Immer prüfen')).toHaveLength(3)
    expect(within(instructionRow).queryByRole('switch')).toBeNull()
  })

  it('kodiert keine eigene Sperrliste: ohne schaltbare Zelle gibt es keinen Schalter', async () => {
    stubApi({ initial: { enabled_cells: [], switchable_cells: [] } })
    renderSection()
    await waitFor(() => expect(document.querySelectorAll('[data-locked-cell]')).toHaveLength(12))
    expect(screen.queryByRole('switch')).toBeNull()
  })

  it('schaltet nicht ohne die sichtbare Warnliste ein: Dialog mit allen acht Punkten zuerst', async () => {
    const { puts } = stubApi()
    renderSection()
    fireEvent.click(await screen.findByRole('switch'))

    const dialog = await screen.findByRole('dialog')
    // Nichts gesendet, solange nicht bestätigt.
    expect(puts).toHaveLength(0)
    const items = within(dialog).getAllByRole('listitem')
    expect(items).toHaveLength(8)
    expect(items[0]).toHaveTextContent('Ein Satz kann Fakt und Anweisung zugleich sein.')
    expect(items[7]).toHaveTextContent('Zurücknehmen hilft erst, wenn jemand den Fehler bemerkt.')

    const confirm = within(dialog).getByRole('button', { name: 'Automatisch freigeben' })
    expect(confirm).toBeDisabled()
    expect(confirm).toHaveAccessibleDescription(
      'Bitte zuerst bestätigen, dass du die Liste gelesen hast.',
    )
    fireEvent.click(within(dialog).getByLabelText('Ich habe gelesen, was automatische Freigabe nicht abfängt.'))
    expect(confirm).toBeEnabled()
    fireEvent.click(confirm)

    await waitFor(() => expect(puts).toEqual([{ enabled_cells: [{ row: 'user_fact', origin: 'user_stated' }] }]))
    await waitFor(() => expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true'))
    expect(notify.success).toHaveBeenCalledWith(
      'Gilt ab jetzt für neue Einträge. Was schon wartet, bleibt zur Freigabe.',
    )
  })

  it('Abbrechen im Dialog sendet nichts und lässt die Zelle aus', async () => {
    const { puts } = stubApi()
    renderSection()
    fireEvent.click(await screen.findByRole('switch'))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(puts).toHaveLength(0)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
  })

  it('verlangt die Bestätigung bei jedem Einschalten neu', async () => {
    stubApi()
    renderSection()
    fireEvent.click(await screen.findByRole('switch'))
    let dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('checkbox'))
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    fireEvent.click(screen.getByRole('switch'))
    dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('checkbox')).not.toBeChecked()
    expect(within(dialog).getByRole('button', { name: 'Automatisch freigeben' })).toBeDisabled()
  })

  it('schaltet sofort aus, ohne Dialog, mit Toast', async () => {
    const { puts } = stubApi({ initial: policy(true) })
    renderSection()
    const toggle = await screen.findByRole('switch')
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(toggle)
    await waitFor(() => expect(puts).toEqual([{ enabled_cells: [] }]))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false'))
    expect(notify.success).toHaveBeenCalledWith(
      'Automatische Freigabe aus. Neue Einträge landen wieder zur Freigabe.',
    )
  })

  it('bleibt bei einem Speicherfehler auf dem Serverstand und zeigt den Fehler', async () => {
    stubApi({ initial: policy(true), putStatus: 500 })
    renderSection()
    fireEvent.click(await screen.findByRole('switch'))
    expect(await screen.findByTestId('error-alert')).toBeInTheDocument()
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
  })

  it('zeigt bei 403 (Token-Sitzung) keinen Schalter, sondern den Hinweis', async () => {
    stubApi({ policyStatus: 403 })
    renderSection()
    expect(await screen.findByText('Nur mit echter Anmeldung änderbar.')).toBeInTheDocument()
    expect(screen.queryByRole('switch')).toBeNull()
  })

  it('warnt, wenn eine Zelle an und der Wächter aus ist', async () => {
    stubApi({ initial: policy(true), guardMode: 'off' })
    renderSection()
    expect(await screen.findByText('Der Memory-Wächter ist aus.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Wächter einstellen' })).toHaveAttribute('href', '#memory-guard')
  })

  it('warnt nicht, solange alles aus ist', async () => {
    stubApi({ initial: policy(false), guardMode: 'off' })
    renderSection()
    await screen.findByRole('switch')
    expect(screen.queryByText('Der Memory-Wächter ist aus.')).toBeNull()
  })

  it('hält die acht Punkte dauerhaft im Abschnitt sichtbar (ohne Checkbox)', async () => {
    stubApi()
    renderSection()
    await screen.findByRole('switch')
    const disclosure = screen.getByTestId('auto-approval-limits-disclosure')
    expect(within(disclosure).getAllByRole('listitem')).toHaveLength(8)
    expect(within(disclosure).queryByRole('checkbox')).toBeNull()
  })

  it('zeigt kein Schloss- und kein Haken-Symbol (ADR 4.3)', async () => {
    stubApi({ initial: policy(true) })
    const { container } = renderSection()
    await screen.findByRole('switch')
    fireEvent.click(container.querySelector('summary')!)
    expect(container.querySelector('[class*="lucide-lock"], [class*="lucide-check"], [class*="lucide-shield"]')).toBeNull()
  })

  it('wird unter md zur Liste je Art, mit demselben einen Schalter', async () => {
    viewport.mobile = true
    stubApi()
    renderSection()
    expect(await screen.findByRole('switch', { name: 'Nutzerfakt Von dir gesagt' })).toBeInTheDocument()
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.getAllByRole('switch')).toHaveLength(1)
    // Komplett gesperrte Zeilen mit gleichem Grund sind zusammengefasst.
    expect(screen.getAllByText('Alle Herkünfte')).toHaveLength(3)
  })

  it('öffnet den Dialog unter md als Bottom-Sheet mit allen acht Punkten', async () => {
    viewport.mobile = true
    stubApi()
    renderSection()
    fireEvent.click(await screen.findByRole('switch'))
    const sheet = await screen.findByRole('dialog')
    expect(within(sheet).getAllByRole('listitem')).toHaveLength(8)
  })
})

// ADR-0053 4.3: Die Oberfläche verspricht nie „sicher“. Geprüft werden alle
// Texte, die diese Karte neu einführt oder ändert, in beiden Sprachen.
describe('Locale-Texte der Auto-Freigabe', () => {
  const FORBIDDEN = /sicher|secure|safe|geschützt|garantiert|guarantee|protected/i

  function strings(node: unknown, path: string, out: Array<[string, string]>) {
    if (typeof node === 'string') {
      out.push([path, node])
      return
    }
    if (node !== null && typeof node === 'object') {
      for (const [key, value] of Object.entries(node)) strings(value, `${path}.${key}`, out)
    }
  }

  for (const [locale, tree] of [['de', de], ['en', en]] as const) {
    it(`enthält in ${locale} kein „sicher“/„secure“/„safe“`, () => {
      const out: Array<[string, string]> = []
      strings(tree.learning.autoPolicy, 'learning.autoPolicy', out)
      strings(tree.agents.form.memory.help, 'agents.form.memory.help', out)
      strings(tree.agents.form.memory.mode.auto, 'agents.form.memory.mode.auto', out)
      expect(out.length).toBeGreaterThan(40)
      expect(out.filter(([, text]) => FORBIDDEN.test(text))).toEqual([])
    })

    it(`führt in ${locale} genau die acht Punkte aus ADR 4.3`, () => {
      const limits = tree.learning.autoPolicy.limits as Record<string, unknown>
      for (const key of AUTO_APPROVAL_LIMIT_KEYS) {
        expect(limits[key]).toEqual({ title: expect.any(String), body: expect.any(String) })
      }
      expect(AUTO_APPROVAL_LIMIT_KEYS).toHaveLength(8)
    })
  }
})
