import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type {
  CaseRead,
  FollowUpReport,
  MeasureEvent,
  MeasureRead,
  MeasureState,
  SessionRead,
  WorkspaceRole,
} from '@/api/types'
import de from '@/i18n/locales/de.json'
import en from '@/i18n/locales/en.json'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { ChangeSheet, type ChangeSheetData } from './ChangeSheet'

// E5e: Aktionen an der Aenderung (Neuschnitt §1, §4; E5-Delta §0.3, §4.2,
// §4.3, §8). Gerendert ueber das Sheet, weil die Freischaltung von „Hat es
// gewirkt?“ am Server-Bericht haengt (QE6) und die Leiste dort sitzt.

const api = vi.hoisted(() => ({
  getFollowUp: vi.fn(),
  listPersonaVersions: vi.fn(),
  listPlaybookVersions: vi.fn(),
  listResourceVersions: vi.fn(),
  listExternalToolVersions: vi.fn(),
  listSystemPromptTemplateVersions: vi.fn(),
  linkMeasureDraft: vi.fn(),
  reviewMeasure: vi.fn(),
  withdrawMeasure: vi.fn(),
}))
vi.mock('@/api/useApi', () => ({ useApi: () => api }))

let role: WorkspaceRole | null = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

const MUTATIONS = ['linkMeasureDraft', 'reviewMeasure', 'withdrawMeasure'] as const

function ev(
  id: string,
  event: MeasureEvent['event'],
  extra: Partial<MeasureEvent> = {},
): MeasureEvent {
  return {
    id,
    measure_id: 'm1',
    event,
    actor_kind: 'agent',
    actor_id: null,
    version_entity_type: null,
    version_id: null,
    verdict: null,
    metrics: null,
    note: null,
    created_at: '2026-09-26T09:00:00Z',
    ...extra,
  }
}

const linked = ev('e1', 'draft_linked', { version_entity_type: 'playbook', version_id: 'v4' })
const activated = ev('e2', 'activated', {
  actor_kind: 'system',
  version_entity_type: 'playbook',
  version_id: 'v4',
  created_at: '2026-09-28T09:00:00Z',
})

function measure(overrides: Partial<MeasureRead> = {}): MeasureRead {
  return {
    id: 'm1',
    workspace_id: 'ws-1',
    agent_id: 'a1',
    session_id: 's1',
    case_ids: ['c1', 'c2', 'c3'],
    target: 'playbook',
    entity_id: 'pb1',
    change_summary: 'Frist aus dem Playbook lesen.',
    test_case_id: 't1',
    success_criterion: 'Frist in keinem Prüffall falsch.',
    counterposition: '',
    follow_up_at: null,
    state: 'activated',
    events: [linked, activated],
    created_at: '2026-09-25T10:00:00Z',
    ...overrides,
  }
}

const session = {
  id: 's1',
  agent_id: 'a1',
  follow_up_at: '2026-10-10',
  created_at: '2026-09-25T10:00:00Z',
} as unknown as SessionRead

const caseRow = (id: string, status: CaseRead['status']) =>
  ({ id, status, expected_behavior: `Erwartung ${id}` }) as unknown as CaseRead

// Zwei geaenderte, eine verworfene Rueckmeldung, eine fremde (nicht in der Aenderung).
const CASES = [
  caseRow('c1', 'addressed'),
  caseRow('c2', 'addressed'),
  caseRow('c3', 'dismissed'),
  caseRow('c9', 'addressed'),
]

function report(overrides: Partial<FollowUpReport> = {}): FollowUpReport {
  return {
    measure_id: 'm1',
    state: 'activated',
    follow_up_at: '2026-10-10',
    due: true,
    reviewable: true,
    before: null,
    after: null,
    recurrence: null,
    min_uses: 30,
    insufficient: false,
    ...overrides,
  }
}

function data(overrides: Partial<MeasureRead> = {}): ChangeSheetData {
  return {
    measure: measure(overrides),
    index: 1,
    session,
    agentName: 'Support',
    element: 'Playbook „Erstattung“',
    testCase: null,
    cases: CASES,
    people: { agentById: new Map(), memberById: new Map() },
  }
}

const onClose = vi.fn()
const onGone = vi.fn()
const onChanged = vi.fn()

function renderSheet(value: ChangeSheetData) {
  return renderInRoutes(
    <ChangeSheet
      data={value}
      onClose={onClose}
      onGone={onGone}
      onChanged={onChanged}
      fallbackFocus={() => null}
    />,
    {
      path: '/w/:workspaceId/agents/:agentId/reviews/:sessionId',
      initialEntries: ['/w/ws-1/agents/a1/reviews/s1'],
    },
  )
}

function mockMobile(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
}

async function sheet() {
  return screen.findByTestId('change-sheet')
}

/** `brand`-Knoepfe/-Links im Sheet (die Variante setzt `bg-brand`). */
function brandActions(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>('button, a')].filter((element) =>
    element.className.split(/\s+/).includes('bg-brand'),
  )
}

function openMore() {
  fireEvent.pointerDown(screen.getByTestId('change-more'), { button: 0, ctrlKey: false })
}

function problem(status: number, reason: string, detail = 'Server-Detail.'): ApiError {
  return new ApiError(status, detail, { detail, reason })
}

beforeEach(() => {
  vi.clearAllMocks()
  role = 'editor'
  mockMobile(false)
  api.getFollowUp.mockResolvedValue(report())
  api.listPlaybookVersions.mockResolvedValue([
    { id: 'v2', version: 2, status: 'inactive' },
    { id: 'v3', version: 3, status: 'active' },
    { id: 'v4', version: 4, status: 'draft' },
    { id: 'v5', version: 5, status: 'review' },
  ])
  api.linkMeasureDraft.mockResolvedValue(linked)
  api.reviewMeasure.mockResolvedValue(ev('e3', 'reviewed'))
  api.withdrawMeasure.mockResolvedValue({ event: ev('e4', 'withdrawn'), cases_reset: [] })
})

afterEach(() => {
  Reflect.deleteProperty(window, 'matchMedia')
})

// --- Leiste je Zustand (E5-Delta §4.2) ------------------------------------

describe('ChangeActions: Leiste je Zustand', () => {
  it('Vereinbart, Ziel versioniert: brand „Entwurf verknüpfen…“, im Menü „Zurückziehen…“', async () => {
    renderSheet(data({ state: 'agreed', events: [] }))
    const bar = await screen.findByTestId('change-actions')
    expect(brandActions(bar).map((element) => element.textContent)).toEqual(['Entwurf verknüpfen…'])
    expect(screen.queryByTestId('change-review')).toBeNull()
    openMore()
    expect(await screen.findByRole('menuitem', { name: 'Zurückziehen…' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /Entwurf/ })).toBeNull()
  })

  it.each(['tool_policy', 'memory'] as const)(
    'Vereinbart, Ziel ohne Versionen (%s), noch nicht fällig: keine brand, Hinweis im Menü',
    async (target) => {
      // QE6: der Server sagt `reviewable: false` (vor dem Nachkontroll-Datum).
      api.getFollowUp.mockResolvedValue(report({ state: 'agreed', due: false, reviewable: false }))
      renderSheet(data({ state: 'agreed', events: [], target, entity_id: null }))
      const bar = await screen.findByTestId('change-actions')
      await waitFor(() => expect(api.getFollowUp).toHaveBeenCalledWith('m1'))
      expect(brandActions(bar)).toEqual([])
      expect(screen.queryByTestId('change-review')).toBeNull()
      openMore()
      expect(await screen.findByTestId('change-no-versions')).toHaveTextContent(
        'Für dieses Ziel gibt es keine Versionen. Ein Entwurf lässt sich nicht verknüpfen.',
      )
      expect(screen.getByRole('menuitem', { name: 'Zurückziehen…' })).toBeInTheDocument()
    },
  )

  it('QE6: Ziel ohne Versionen, fällig: „Hat es gewirkt?“ ohne `activated`, weil der Server es erlaubt', async () => {
    api.getFollowUp.mockResolvedValue(report({ state: 'agreed', due: true, reviewable: true }))
    renderSheet(data({ state: 'agreed', events: [], target: 'tool_policy', entity_id: null }))
    expect(await screen.findByTestId('change-review')).toBeInTheDocument()
    const bar = screen.getByTestId('change-actions')
    expect(brandActions(bar).map((element) => element.textContent)).toEqual(['Antwort speichern'])
  })

  it('Entwurf verknüpft: „Zum Entwurf“ (default, Link), im Menü „Anderen Entwurf verknüpfen…“ und „Zurückziehen…“', async () => {
    renderSheet(data({ state: 'draft_linked', events: [linked] }))
    const bar = await screen.findByTestId('change-actions')
    expect(brandActions(bar)).toEqual([])
    expect(within(bar).getByRole('link', { name: 'Zum Entwurf' })).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks/pb1?tab=versions',
    )
    openMore()
    const items = (await screen.findAllByRole('menuitem')).map((item) => item.textContent)
    expect(items).toEqual(['Anderen Entwurf verknüpfen…', 'Zurückziehen…'])
  })

  it.each(['activated', 'follow_up_prepared'] as const)(
    '%s: brand „Antwort speichern“ (aus, bis eine Antwort gewählt ist), im Menü nur „Zurückziehen…“',
    async (state) => {
      renderSheet(data({ state }))
      await screen.findByTestId('change-review')
      const bar = screen.getByTestId('change-actions')
      const brands = brandActions(bar)
      expect(brands.map((element) => element.textContent)).toEqual(['Antwort speichern'])
      expect(brands[0]).toBeDisabled()
      openMore()
      const items = (await screen.findAllByRole('menuitem')).map((item) => item.textContent)
      expect(items).toEqual(['Zurückziehen…'])
    },
  )

  it.each(['effective', 'ineffective', 'not_measurable', 'withdrawn'] as const)(
    'Endzustand %s: keine Leiste, keine Antwort',
    async (state) => {
      renderSheet(data({ state }))
      await sheet()
      expect(screen.queryByTestId('change-actions')).toBeNull()
      expect(screen.queryByTestId('change-review')).toBeNull()
      expect(screen.queryByTestId('change-more')).toBeNull()
    },
  )

  it('aktiviert, Server sagt nicht einstufbar: keine Antwort (eine Quelle)', async () => {
    api.getFollowUp.mockResolvedValue(report({ reviewable: false }))
    renderSheet(data({ state: 'activated' }))
    await screen.findByTestId('follow-up-figures')
    expect(screen.queryByTestId('change-review')).toBeNull()
  })

  it('Kennzahlen-Fehler: Antwort bleibt bei versioniertem, aktiviertem Ziel möglich', async () => {
    api.getFollowUp.mockRejectedValue(new ApiError(500, 'kaputt'))
    renderSheet(data({ state: 'activated' }))
    await screen.findByTestId('follow-up-error')
    expect(screen.getByTestId('change-review')).toBeInTheDocument()
  })

  it.each<MeasureState>([
    'agreed',
    'draft_linked',
    'activated',
    'follow_up_prepared',
  ])('%s: kein Element setzt Rückmeldungen direkt auf „In Arbeit“ oder „Hat gewirkt“', async (state) => {
    renderSheet(data({ state, events: state === 'agreed' ? [] : state === 'draft_linked' ? [linked] : [linked, activated] }))
    await screen.findByTestId('change-actions')
    openMore()
    await screen.findAllByRole('menuitem')
    const controls = [
      ...screen.queryAllByRole('button'),
      ...screen.queryAllByRole('menuitem'),
      ...screen.queryAllByRole('link'),
    ]
    for (const control of controls) {
      expect(control.textContent ?? '').not.toMatch(/In Arbeit|als geändert|In progress|Verified/i)
    }
    // Die einzigen Radios sind die drei Antworten auf „Hat es gewirkt?“.
    const radios = screen.queryAllByRole('radio')
    expect(radios.length === 0 || radios.length === 3).toBe(true)
  })
})

// --- „Hat es gewirkt?“ -----------------------------------------------------

describe('ChangeActions: Hat es gewirkt?', () => {
  it('fieldset mit legend, Hinweis, nichts vorausgewählt; Folgen-Satz mit Zählung', async () => {
    renderSheet(data())
    const review = await screen.findByTestId('change-review')
    expect(within(review).getByRole('group', { name: 'Hat es gewirkt?' })).toBeInTheDocument()
    expect(within(review).getByTestId('change-review-human-only')).toHaveTextContent(
      'Nur Menschen beantworten das. Der Builder bereitet vor, entscheidet aber nicht.',
    )
    const radios = within(review).getAllByRole('radio')
    expect(radios.map((radio) => radio.getAttribute('aria-checked'))).toEqual(['false', 'false', 'false'])
    expect(within(review).getByRole('radiogroup')).toHaveAttribute(
      'aria-describedby',
      expect.stringContaining(within(review).getByTestId('change-review-effect').id),
    )
    const effect = within(review).getByTestId('change-review-effect')
    expect(effect).toHaveAttribute('aria-live', 'polite')
    expect(effect).toBeEmptyDOMElement()

    // c1, c2 geaendert; c3 verworfen; c9 gehoert nicht zur Aenderung.
    fireEvent.click(within(review).getByRole('radio', { name: 'Ja, hat gewirkt' }))
    expect(effect).toHaveTextContent(
      'Die 2 geänderten Rückmeldungen gelten danach als „Hat gewirkt“. Das ist ein Endzustand. 1 weitere Rückmeldung dieser Änderung ändert sich nicht.',
    )
    fireEvent.click(within(review).getByRole('radio', { name: 'Nein, hat nicht gewirkt' }))
    expect(effect).toHaveTextContent(
      'Die 2 geänderten Rückmeldungen gehen auf „Wieder offen“ und erscheinen wieder in der Liste.',
    )
    fireEvent.click(within(review).getByRole('radio', { name: 'Nicht messbar' }))
    expect(effect).toHaveTextContent(
      'Die Rückmeldungen bleiben, wie sie sind. Die Änderung ist damit abgeschlossen.',
    )
    expect(effect).not.toHaveTextContent('weitere Rückmeldung')
  })

  it('Folgen-Satz: Singular und ohne Zusatz, wenn alle Rückmeldungen geändert sind', async () => {
    renderSheet({ ...data({ case_ids: ['c1'] }) })
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Ja, hat gewirkt' }))
    expect(within(review).getByTestId('change-review-effect')).toHaveTextContent(
      'Die 1 geänderte Rückmeldung gilt danach als „Hat gewirkt“. Das ist ein Endzustand.',
    )
    expect(within(review).getByTestId('change-review-effect')).not.toHaveTextContent('weitere')
  })

  it('„Nein“ ohne Notiz: Feldfehler mit aria-invalid und Fokus, kein Request', async () => {
    renderSheet(data())
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Nein, hat nicht gewirkt' }))
    const note = within(review).getByLabelText('Notiz')
    fireEvent.change(note, { target: { value: 'zu kurz' } })
    fireEvent.click(screen.getByRole('button', { name: 'Antwort speichern' }))
    expect(note).toHaveAttribute('aria-invalid', 'true')
    expect(note).toHaveFocus()
    expect(within(review).getByTestId('change-review-note-error')).toHaveTextContent(
      'Bei „Nein, hat nicht gewirkt“ brauchen die Rückmeldungen eine Begründung. Mindestens 10 Zeichen.',
    )
    expect(note).toHaveAttribute('aria-describedby', within(review).getByTestId('change-review-note-error').id)
    expect(api.reviewMeasure).not.toHaveBeenCalled()
  })

  it('„Ja“ ohne Notiz: Notiz optional, Request ohne note; Sheet bleibt offen, Fokus aufs Zustandswort', async () => {
    renderSheet(data())
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Ja, hat gewirkt' }))
    expect(within(review).getByLabelText('Notiz (optional)')).not.toHaveAttribute('aria-invalid')
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Antwort speichern' }))
    })
    expect(api.reviewMeasure).toHaveBeenCalledWith('m1', { verdict: 'effective' })
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('change-state')).toHaveFocus()
    expect(screen.getByTestId('change-review-done')).toHaveTextContent('Beantwortet: Hat gewirkt')
    expect(screen.queryByTestId('change-new-review')).toBeNull()
    expect(screen.getByTestId('change-sheet')).toBeInTheDocument()
  })

  it('„Nein“ mit Notiz: Request mit note, danach Link „Neues Review vorbereiten“ mit Agent und Rückmeldungen', async () => {
    renderSheet(data())
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Nein, hat nicht gewirkt' }))
    fireEvent.change(within(review).getByLabelText('Notiz'), {
      target: { value: '  Frist wieder falsch genannt.  ' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Antwort speichern' }))
    })
    expect(api.reviewMeasure).toHaveBeenCalledWith('m1', {
      verdict: 'ineffective',
      note: 'Frist wieder falsch genannt.',
    })
    expect(screen.getByTestId('change-new-review')).toHaveAttribute(
      'href',
      '/w/ws-1/agents/a1/reviews/prepare?cases=c1,c2,c3',
    )
  })
})

// --- Fehler (E5-Delta §4.3) -------------------------------------------------

describe('ChangeActions: Fehler', () => {
  async function answerYes() {
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Ja, hat gewirkt' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Antwort speichern' }))
    })
    return review
  }

  it('measure_not_found: onGone (Sheet zu, Toast)', async () => {
    api.reviewMeasure.mockRejectedValue(problem(404, 'measure_not_found'))
    renderSheet(data())
    const review = await answerYes()
    expect(onGone).toHaveBeenCalledTimes(1)
    expect(within(review).queryByRole('alert')).toBeNull()
  })

  it('measure_transition_forbidden (409, QE3): neu laden und Text', async () => {
    api.reviewMeasure.mockRejectedValue(problem(409, 'measure_transition_forbidden'))
    renderSheet(data())
    const review = await answerYes()
    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(within(review).getByRole('alert')).toHaveTextContent(
      'Dieser Schritt passt nicht zum aktuellen Stand. Die Änderung wurde neu geladen.',
    )
  })

  it('missing_capability (403): Rechte-Text ab Rolle Editor', async () => {
    api.reviewMeasure.mockRejectedValue(problem(403, 'missing_capability'))
    renderSheet(data())
    const review = await answerYes()
    expect(within(review).getByRole('alert')).toHaveTextContent(
      'Dafür fehlen dir die Rechte (ab Rolle Editor).',
    )
  })

  it.each(['session_cases_invalid', 'measure_test_case_required', 'unbekannt'])(
    'sonst (%s): problem.detail des Servers',
    async (reason) => {
      api.reviewMeasure.mockRejectedValue(problem(422, reason, 'Detail vom Server.'))
      renderSheet(data())
      const review = await answerYes()
      expect(within(review).getByRole('alert')).toHaveTextContent('Detail vom Server.')
    },
  )

  it('session_cases_invalid und measure_test_case_required haben keinen Key (QE9)', () => {
    for (const locale of [de, en]) {
      const flat = JSON.stringify(locale.sessions)
      expect(flat).not.toMatch(/sessionCasesInvalid|session_cases_invalid|measureTestCaseRequired|measure_test_case_required/)
    }
  })
})

// --- Entwurf verknuepfen ------------------------------------------------------

describe('ChangeActions: Entwurf verknüpfen', () => {
  async function openLink() {
    renderSheet(data({ state: 'agreed', events: [] }))
    fireEvent.click(await screen.findByRole('button', { name: 'Entwurf verknüpfen…' }))
    return screen.findByTestId('change-link-draft-dialog')
  }

  it('Baustein fest, nur Entwurf/Zur Freigabe, neueste zuerst; Hilfe-Satz', async () => {
    const dialog = await openLink()
    expect(within(dialog).getByTestId('change-link-draft-element')).toHaveTextContent('Playbook „Erstattung“')
    const select = within(dialog).getByLabelText('Version')
    await waitFor(() => expect(select).not.toBeDisabled())
    const options = within(select).getAllByRole('option').map((option) => option.textContent)
    expect(options).toEqual(['Version wählen', 'v5 · zur Freigabe', 'v4 · Entwurf'])
    expect(dialog).toHaveTextContent('Der Entwurf bleibt Entwurf.')
  })

  it('ohne Auswahl: Feldfehler, kein Request; mit Auswahl: Request und neu laden', async () => {
    const dialog = await openLink()
    const select = within(dialog).getByLabelText('Version')
    await waitFor(() => expect(select).not.toBeDisabled())
    fireEvent.click(within(dialog).getByRole('button', { name: 'Verknüpfen' }))
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(api.linkMeasureDraft).not.toHaveBeenCalled()
    fireEvent.change(select, { target: { value: 'v5' } })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Verknüpfen' }))
    })
    expect(api.linkMeasureDraft).toHaveBeenCalledWith('m1', {
      version_entity_type: 'playbook',
      version_id: 'v5',
    })
    expect(onChanged).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.queryByTestId('change-link-draft-dialog')).toBeNull())
  })

  it('kein Entwurf: Leer-Satz mit Link zum Baustein, Verknüpfen aus', async () => {
    api.listPlaybookVersions.mockResolvedValue([{ id: 'v3', version: 3, status: 'active' }])
    const dialog = await openLink()
    const none = await within(dialog).findByTestId('change-link-draft-none')
    expect(none).toHaveTextContent(
      'Für Playbook „Erstattung“ gibt es noch keinen Entwurf. Lege ihn im Versions-Tab an oder lass ihn vom Builder anlegen.',
    )
    expect(within(none).getByRole('link')).toHaveAttribute('href', '/w/ws-1/playbooks/pb1')
    expect(within(dialog).getByRole('button', { name: 'Verknüpfen' })).toBeDisabled()
  })

  it('test_subject_version_not_found: Text, Auswahl leer, Liste lädt neu', async () => {
    api.linkMeasureDraft.mockRejectedValue(problem(404, 'test_subject_version_not_found'))
    const dialog = await openLink()
    const select = within(dialog).getByLabelText('Version')
    await waitFor(() => expect(select).not.toBeDisabled())
    fireEvent.change(select, { target: { value: 'v4' } })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Verknüpfen' }))
    })
    expect(within(dialog).getByRole('alert')).toHaveTextContent(
      'Diese Version gibt es nicht mehr. Wähle eine andere.',
    )
    await waitFor(() => expect(api.listPlaybookVersions).toHaveBeenCalledTimes(2))
    expect((within(dialog).getByLabelText('Version') as HTMLSelectElement).value).toBe('')
    expect(onGone).not.toHaveBeenCalled()
  })

  it('„Anderen Entwurf verknüpfen…“ öffnet denselben Dialog', async () => {
    renderSheet(data({ state: 'draft_linked', events: [linked] }))
    await screen.findByTestId('change-actions')
    openMore()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Anderen Entwurf verknüpfen…' }))
    expect(await screen.findByTestId('change-link-draft-dialog')).toBeInTheDocument()
  })
})

// --- Zurueckziehen --------------------------------------------------------

describe('ChangeActions: Zurückziehen', () => {
  async function openWithdraw() {
    renderSheet(data())
    await screen.findByTestId('change-actions')
    openMore()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Zurückziehen…' }))
    return screen.findByTestId('change-withdraw-dialog')
  }

  it('QE5 a: Satz zu den Rückmeldungen aus einem Key; destructive Knopf', async () => {
    const dialog = await openWithdraw()
    expect(dialog).toHaveTextContent('Die Änderung wird aufgegeben. Ein verknüpfter Entwurf bleibt Entwurf.')
    expect(within(dialog).getByTestId('change-withdraw-cases')).toHaveTextContent(
      'Rückmeldungen, die gerade in Arbeit sind, gehen zurück auf „Eingeordnet“, sofern keine andere offene Änderung sie enthält.',
    )
    expect(within(dialog).getByRole('button', { name: 'Zurückziehen' }).className).toContain('bg-destructive')
  })

  it('Begründung Pflicht (≥ 10 Zeichen): Feldfehler mit Fokus, dann Request', async () => {
    const dialog = await openWithdraw()
    const field = within(dialog).getByLabelText('Warum wird die Änderung aufgegeben?')
    fireEvent.change(field, { target: { value: 'kurz' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Zurückziehen' }))
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(field).toHaveFocus()
    expect(api.withdrawMeasure).not.toHaveBeenCalled()
    fireEvent.change(field, { target: { value: 'Ziel hat sich erledigt.' } })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Zurückziehen' }))
    })
    expect(api.withdrawMeasure).toHaveBeenCalledWith('m1', { note: 'Ziel hat sich erledigt.' })
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('409 beim Zurückziehen: Text im Dialog, neu laden', async () => {
    api.withdrawMeasure.mockRejectedValue(problem(409, 'measure_transition_forbidden'))
    const dialog = await openWithdraw()
    fireEvent.change(within(dialog).getByLabelText('Warum wird die Änderung aufgegeben?'), {
      target: { value: 'Ziel hat sich erledigt.' },
    })
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Zurückziehen' }))
    })
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Dieser Schritt passt nicht zum aktuellen Stand.')
    expect(onChanged).toHaveBeenCalledTimes(1)
  })
})

// --- Doppel-Submit und Abbrechen ----------------------------------------------

describe('ChangeActions: Doppel-Submit und Abbrechen', () => {
  /** Ein Request, der haengen bleibt, bis der Test ihn aufloest. */
  function pending<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
    let resolve: (value: T) => void = () => undefined
    const promise = new Promise<T>((done) => {
      resolve = done
    })
    return { promise, resolve }
  }

  async function openWithdraw() {
    renderSheet(data())
    await screen.findByTestId('change-actions')
    openMore()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Zurückziehen…' }))
    const dialog = await screen.findByTestId('change-withdraw-dialog')
    fireEvent.change(within(dialog).getByLabelText('Warum wird die Änderung aufgegeben?'), {
      target: { value: 'Ziel hat sich erledigt.' },
    })
    return dialog
  }

  it('Zurückziehen: Knopf während des Requests gesperrt, genau ein Aufruf', async () => {
    const request = pending<{ event: MeasureEvent; cases_reset: string[] }>()
    api.withdrawMeasure.mockReturnValue(request.promise)
    const dialog = await openWithdraw()
    const submit = within(dialog).getByRole('button', { name: 'Zurückziehen' })
    fireEvent.click(submit)
    await waitFor(() => expect(submit).toBeDisabled())
    expect(submit).toHaveAttribute('aria-busy', 'true')
    expect(within(dialog).getByRole('button', { name: 'Abbrechen' })).toBeDisabled()
    fireEvent.click(submit)
    fireEvent.submit(submit.closest('form') as HTMLFormElement)
    expect(api.withdrawMeasure).toHaveBeenCalledTimes(1)
    await act(async () => {
      request.resolve({ event: ev('e4', 'withdrawn'), cases_reset: [] })
      await request.promise
    })
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('Antwort speichern: Knopf während des Requests gesperrt, genau ein Aufruf', async () => {
    const request = pending<MeasureEvent>()
    api.reviewMeasure.mockReturnValue(request.promise)
    renderSheet(data())
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Ja, hat gewirkt' }))
    const submit = screen.getByRole('button', { name: 'Antwort speichern' })
    fireEvent.click(submit)
    await waitFor(() => expect(submit).toBeDisabled())
    expect(submit).toHaveAttribute('aria-busy', 'true')
    // Zweiter Weg an der gesperrten Schaltflaeche vorbei: implizites Absenden.
    fireEvent.click(submit)
    fireEvent.submit(within(review).getByRole('group', { name: 'Hat es gewirkt?' }).closest('form') as HTMLFormElement)
    expect(api.reviewMeasure).toHaveBeenCalledTimes(1)
    await act(async () => {
      request.resolve(ev('e3', 'reviewed'))
      await request.promise
    })
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('Verknüpfen: Knopf während des Requests gesperrt, genau ein Aufruf', async () => {
    const request = pending<MeasureEvent>()
    api.linkMeasureDraft.mockReturnValue(request.promise)
    renderSheet(data({ state: 'agreed', events: [] }))
    fireEvent.click(await screen.findByRole('button', { name: 'Entwurf verknüpfen…' }))
    const dialog = await screen.findByTestId('change-link-draft-dialog')
    const select = within(dialog).getByLabelText('Version')
    await waitFor(() => expect(select).not.toBeDisabled())
    fireEvent.change(select, { target: { value: 'v4' } })
    const submit = within(dialog).getByRole('button', { name: 'Verknüpfen' })
    fireEvent.click(submit)
    await waitFor(() => expect(submit).toBeDisabled())
    expect(submit).toHaveAttribute('aria-busy', 'true')
    fireEvent.click(submit)
    fireEvent.submit(submit.closest('form') as HTMLFormElement)
    expect(api.linkMeasureDraft).toHaveBeenCalledTimes(1)
    await act(async () => {
      request.resolve(linked)
      await request.promise
    })
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('Abbrechen im Dialog „Zurückziehen“ mit gültiger Begründung: Dialog zu, kein Request', async () => {
    const dialog = await openWithdraw()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))
    await waitFor(() => expect(screen.queryByTestId('change-withdraw-dialog')).toBeNull())
    expect(api.withdrawMeasure).not.toHaveBeenCalled()
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('unter md: Feldfehler der Notiz wird nach dem Fokus ganz ins Bild geholt', async () => {
    mockMobile(true)
    const scroll = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scroll
    try {
      renderSheet(data())
      expect(await screen.findByTestId('change-sheet')).toHaveClass('scroll-pb-36')
      const review = await screen.findByTestId('change-review')
      fireEvent.click(within(review).getByRole('radio', { name: 'Nein, hat nicht gewirkt' }))
      fireEvent.click(screen.getByRole('button', { name: 'Antwort speichern' }))
      const field = within(review).getByTestId('change-review-note-field')
      expect(within(field).getByTestId('change-review-note-error')).toBeInTheDocument()
      expect(scroll.mock.contexts).toContain(field)
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })
})

// --- viewer (Mutationsprobe) --------------------------------------------------

describe('ChangeActions: viewer', () => {
  it.each<[MeasureState, MeasureEvent[]]>([
    ['agreed', []],
    ['draft_linked', [linked]],
    ['activated', [linked, activated]],
  ])('viewer (%s): keine Aktionen, keine Antwort, keine mutierenden Requests', async (state, events) => {
    role = 'viewer'
    renderSheet(data({ state, events }))
    await sheet()
    // Kennzahlen/Versionen geladen, damit eine spaete Leiste auffiele.
    await waitFor(() => expect(screen.getByTestId('change-fields')).toBeInTheDocument())
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.queryByTestId('change-actions')).toBeNull()
    expect(screen.queryByTestId('change-review')).toBeNull()
    expect(screen.queryByRole('radio')).toBeNull()
    for (const name of MUTATIONS) expect(api[name]).not.toHaveBeenCalled()
  })
})

// --- 390 px -----------------------------------------------------------------

describe('ChangeActions: unter md', () => {
  it('Leiste unten fixiert, „Weitere Aktionen“ vor der brand-Aktion, beide volle Breite', async () => {
    mockMobile(true)
    renderSheet(data())
    const bar = await screen.findByTestId('change-actions')
    expect(bar.className).toContain('max-md:sticky')
    expect(bar.className).toContain('max-md:bottom-0')
    const buttons = within(bar).getAllByRole('button')
    expect(buttons.map((button) => button.textContent)).toEqual(['Weitere Aktionen', 'Antwort speichern'])
    for (const button of buttons) expect(button.className).toContain('w-full')
  })
})

// --- axe: je Zustand und je Dialog ein eigenes it() ------------------------

describe('ChangeActions a11y', () => {
  it('a11y: Vereinbart (versioniert)', async () => {
    renderSheet(data({ state: 'agreed', events: [] }))
    await screen.findByTestId('change-actions')
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Vereinbart (ohne Versionen, fällig)', async () => {
    api.getFollowUp.mockResolvedValue(report({ state: 'agreed' }))
    renderSheet(data({ state: 'agreed', events: [], target: 'memory', entity_id: null }))
    await screen.findByTestId('change-review')
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Entwurf verknüpft', async () => {
    renderSheet(data({ state: 'draft_linked', events: [linked] }))
    await screen.findByTestId('change-actions')
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Aktiviert mit gewählter Antwort und Feldfehler', async () => {
    renderSheet(data())
    const review = await screen.findByTestId('change-review')
    fireEvent.click(within(review).getByRole('radio', { name: 'Nein, hat nicht gewirkt' }))
    fireEvent.click(screen.getByRole('button', { name: 'Antwort speichern' }))
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Kennzahlen bereit', async () => {
    renderSheet(data({ state: 'follow_up_prepared' }))
    await screen.findByTestId('change-review')
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Endzustand', async () => {
    renderSheet(data({ state: 'effective' }))
    await screen.findByTestId('follow-up-figures')
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Dialog Entwurf verknüpfen', async () => {
    renderSheet(data({ state: 'agreed', events: [] }))
    fireEvent.click(await screen.findByRole('button', { name: 'Entwurf verknüpfen…' }))
    const dialog = await screen.findByTestId('change-link-draft-dialog')
    await waitFor(() => expect(within(dialog).getByLabelText('Version')).not.toBeDisabled())
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)

  it('a11y: Dialog Zurückziehen', async () => {
    renderSheet(data())
    await screen.findByTestId('change-actions')
    openMore()
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Zurückziehen…' }))
    await screen.findByTestId('change-withdraw-dialog')
    expect(await axe(document.body)).toHaveNoViolations()
  }, 15_000)
})
