import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Persona, PersonaContent, Playbook } from '@/api/types'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'

import { PersonaPlaybooksCard } from './PersonaPlaybooksCard'

// getPersona wird von der Card selbst-enthaltend aufgerufen, um die im
// Persona-Inhalt referenzierten Playbook-IDs (Modus/Body-Pill) zu bestimmen.
// `mockApi` ist stabil (wie der echte, memoisierte `useApi`), sonst triggert
// der Effekt-Dependency `api` bei jedem Render einen erneuten Fetch (Loop).
const { mockGetPersona, mockApi } = vi.hoisted(() => {
  const getPersona = vi.fn()
  return { mockGetPersona: getPersona, mockApi: { getPersona } }
})

vi.mock('@/api/useApi', () => ({
  useApi: () => mockApi,
}))
vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))
vi.mock('@/hooks/usePersonaPlaybooks', () => ({
  usePersonaPlaybooks: vi.fn(),
}))

/** Minimal-Persona mit gegebenem Inhalt — nur `content` liest die Card. */
function personaContent(content: Partial<PersonaContent> = {}): Persona {
  return {
    content: { description: '', system_prompt: '', traits: [], ...content },
  } as unknown as Persona
}

/** Baut einen Profil-Body-Block mit einer Playbook-Placeholder-Pill. */
function playbookPillBlocks(targetId: string): PersonaContent['content'] {
  return {
    description: '',
    blocks: [
      {
        id: 'b1',
        type: 'paragraph',
        content: [
          { type: 'placeholder', props: { kind: 'playbook', target_id: targetId, label: '' } },
        ],
      },
    ],
  } as unknown as PersonaContent['content']
}

function playbook(overrides: Partial<Playbook> = {}): Playbook {
  return {
    id: 'pb1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Coaching',
    current_version: 1,
    current_status: 'active',
    type: 'workflow',
    tags: [],
    triggers: null,
    content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
    created_at: 't',
    updated_at: 't',
    ...overrides,
  }
}

type HookState = ReturnType<typeof usePersonaPlaybooks>

function hookState(overrides: Partial<HookState> = {}): HookState {
  return {
    playbooks: [],
    linked: [],
    linkedIds: [],
    loading: false,
    saving: false,
    error: null,
    toggle: vi.fn(),
    save: vi.fn(async () => true),
    cancel: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  }
}

function renderCard(state: HookState, canEdit = true) {
  vi.mocked(usePersonaPlaybooks).mockReturnValue(state)
  return render(
    <MemoryRouter>
      <PersonaPlaybooksCard personaId="p1" canEdit={canEdit} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(usePersonaPlaybooks).mockReset()
  // Default: kein Inhalt referenziert ein Playbook → keine Referenz-Badges.
  mockGetPersona.mockReset()
  mockGetPersona.mockResolvedValue(personaContent())
})

describe('PersonaPlaybooksCard — Anzeige-Modus', () => {
  it('rendert verknuepfte Playbooks als Links mit Status, Composite-Badge und Meta', () => {
    const composite = playbook({
      id: 'pb2',
      name: 'Onboarding',
      current_status: 'draft',
      is_composite: true,
      type: 'checklist',
      triggers: 'neuer kunde, kickoff',
    })
    const linked = [playbook(), composite]
    renderCard(hookState({ playbooks: linked, linked }))

    const link = screen.getByRole('link', { name: 'Coaching' })
    expect(link).toHaveAttribute('href', '/w/ws-1/playbooks/pb1')
    expect(screen.getByRole('link', { name: 'Onboarding' })).toHaveAttribute(
      'href',
      '/w/ws-1/playbooks/pb2',
    )
    // StatusBadges beider Playbooks.
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(screen.getByText('Entwurf')).toBeInTheDocument()
    // Composite-Badge nur am Composite.
    expect(screen.getAllByText('Composite')).toHaveLength(1)
    // Meta: Typ + Trigger-Anzahl.
    expect(screen.getByText('workflow')).toBeInTheDocument()
    expect(screen.getByText(/checklist · 2 Trigger/)).toBeInTheDocument()
  })

  it('zeigt einen EmptyState ohne Verknuepfungen', () => {
    renderCard(hookState({ playbooks: [playbook()], linked: [] }))

    expect(screen.getByText('Keine Playbooks verknüpft.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Coaching' })).not.toBeInTheDocument()
  })

  it('blendet den Bearbeiten-Button ohne canEdit aus (Viewer/managed)', () => {
    renderCard(hookState({ playbooks: [playbook()], linked: [playbook()] }), false)

    expect(
      screen.queryByRole('button', { name: 'Verknüpfungen bearbeiten' }),
    ).not.toBeInTheDocument()
  })
})

describe('PersonaPlaybooksCard — Bearbeiten-Modus', () => {
  it('teilt Playbooks in „Verknüpft" (Entfernen) und „Hinzufügen" (Verknüpfen)', () => {
    const all = [playbook(), playbook({ id: 'pb2', name: 'Brainstorming' })]
    renderCard(hookState({ playbooks: all, linked: [all[0]], linkedIds: ['pb1'] }))

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))

    // Beide Sektionen sind da.
    expect(screen.getByText('Verknüpft')).toBeInTheDocument()
    expect(screen.getByText('Playbook hinzufügen')).toBeInTheDocument()
    expect(screen.getByLabelText('Playbooks durchsuchen')).toBeInTheDocument()

    // „Coaching" ist verknüpft → hat eine Entfernen-Aktion, keine Verknüpfen.
    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entfernen' })).toBeInTheDocument()
    // „Brainstorming" ist verfügbar → hat eine Verknüpfen-Aktion.
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Verknüpfen' })).toBeInTheDocument()

    // Im Bearbeiten-Modus verschwindet der Bearbeiten-Button.
    expect(
      screen.queryByRole('button', { name: 'Verknüpfungen bearbeiten' }),
    ).not.toBeInTheDocument()
  })

  it('ruft toggle beim Verknüpfen eines verfügbaren Playbooks', () => {
    const all = [playbook({ id: 'pb2', name: 'Brainstorming' })]
    const state = hookState({ playbooks: all, linked: [], linkedIds: [] })
    renderCard(state)

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfen' }))

    expect(state.toggle).toHaveBeenCalledWith('pb2')
  })

  it('ruft toggle beim Entfernen eines verknüpften Playbooks', () => {
    const all = [playbook()]
    const state = hookState({ playbooks: all, linked: all, linkedIds: ['pb1'] })
    renderCard(state)

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    fireEvent.click(screen.getByRole('button', { name: 'Entfernen' }))

    expect(state.toggle).toHaveBeenCalledWith('pb1')
  })

  it('filtert die Hinzufügen-Liste ueber das Suchfeld und zeigt den Leerzustand', () => {
    const all = [playbook(), playbook({ id: 'pb2', name: 'Brainstorming' })]
    renderCard(hookState({ playbooks: all, linked: [], linkedIds: [] }))

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    fireEvent.change(screen.getByLabelText('Playbooks durchsuchen'), {
      target: { value: 'brain' },
    })

    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Playbooks durchsuchen'), {
      target: { value: 'xyz' },
    })
    expect(screen.getByText('Keine Playbooks für diese Suche.')).toBeInTheDocument()
  })

  it('Abbrechen verwirft lokale Aenderungen und kehrt zur Anzeige zurueck', () => {
    const all = [playbook()]
    const state = hookState({ playbooks: all, linked: all, linkedIds: ['pb1'] })
    renderCard(state)

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))

    expect(state.cancel).toHaveBeenCalledTimes(1)
    expect(state.save).not.toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'Coaching' })).toBeInTheDocument()
  })

  it('Speichern ruft save und verlaesst den Bearbeiten-Modus bei Erfolg', async () => {
    const all = [playbook()]
    const state = hookState({ playbooks: all, linked: all, linkedIds: ['pb1'] })
    renderCard(state)

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen speichern' }))

    await waitFor(() => {
      expect(state.save).toHaveBeenCalledTimes(1)
    })
    expect(await screen.findByRole('link', { name: 'Coaching' })).toBeInTheDocument()
  })

  it('bleibt im Bearbeiten-Modus, wenn save fehlschlaegt', async () => {
    const all = [playbook()]
    const state = hookState({
      playbooks: all,
      linked: all,
      linkedIds: ['pb1'],
      save: vi.fn(async () => false),
    })
    renderCard(state)

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen speichern' }))

    await waitFor(() => {
      expect(state.save).toHaveBeenCalledTimes(1)
    })
    expect(screen.getByLabelText('Playbooks durchsuchen')).toBeInTheDocument()
  })
})

describe('PersonaPlaybooksCard — Referenz-Hinweis (ehrlich, nicht sperrend)', () => {
  const referencedLabel = 'Im Text referenziert'

  it('zeigt den Badge im Anzeige-Modus, wenn ein Modus das Playbook bindet', async () => {
    const linked = [playbook()]
    mockGetPersona.mockResolvedValue(
      personaContent({
        modes: [
          {
            name: 'Standard',
            is_default: true,
            identity_add: [],
            output_style_override: [],
            anti_patterns: [],
            playbook_id: 'pb1',
          },
        ],
      }),
    )
    renderCard(hookState({ playbooks: linked, linked }))

    expect(await screen.findByText(referencedLabel)).toBeInTheDocument()
  })

  it('zeigt den Badge, wenn eine Body-Pill das Playbook referenziert', async () => {
    const linked = [playbook()]
    mockGetPersona.mockResolvedValue(
      personaContent({ content: playbookPillBlocks('pb1') }),
    )
    renderCard(hookState({ playbooks: linked, linked }))

    expect(await screen.findByText(referencedLabel)).toBeInTheDocument()
  })

  it('zeigt KEINEN Badge fuer ein verknuepftes, aber nicht referenziertes Playbook', async () => {
    const linked = [playbook()]
    mockGetPersona.mockResolvedValue(personaContent({ content: playbookPillBlocks('other') }))
    renderCard(hookState({ playbooks: linked, linked }))

    // Warten, bis der Fetch aufgeloest ist, damit ein spaeter Badge nicht durchrutscht.
    await waitFor(() => expect(mockGetPersona).toHaveBeenCalled())
    expect(screen.queryByText(referencedLabel)).not.toBeInTheDocument()
  })

  it('zeigt den Badge im Bearbeiten-Modus und blockiert das Entfernen NICHT', async () => {
    const linked = [playbook()]
    const state = hookState({ playbooks: linked, linked, linkedIds: ['pb1'] })
    mockGetPersona.mockResolvedValue(
      personaContent({ content: playbookPillBlocks('pb1') }),
    )
    renderCard(state)

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfungen bearbeiten' }))

    // Referenz-Badge steht in der „Verknüpft"-Zeile …
    expect(await screen.findByText(referencedLabel)).toBeInTheDocument()
    // … und die Entfernen-Aktion bleibt aktiv (kein Lock).
    const remove = screen.getByRole('button', { name: 'Entfernen' })
    expect(remove).toBeEnabled()
    fireEvent.click(remove)
    expect(state.toggle).toHaveBeenCalledWith('pb1')
  })
})

// Responsive-Vertrag #571 (Haelfte A). Die 40 px stammen aus **AK 3 dieses
// Issues**, nicht aus der Norm: `docs/frontend/design-language.md` §11 ist die
// einzige Quelle des Floors und setzt ihn auf >= 32 px, `size="sm"` (36 px)
// bleibt dort ausdruecklich zulaessig. Dieses Paket hebt den Wert unterhalb
// `md` an, weil sein Akzeptanzkriterium es verlangt.
//
// jsdom hat kein Layout, deshalb Klassen-Vertraege; die Layout-Aussagen sind in
// `.claude/plan/2026-09-23-1500_571a-w3-personas-responsive-audit.md` gerendert
// belegt (Chromium gegen das gebaute CSS, 320/375/768/1024 px).
describe('PersonaPlaybooksCard — Responsive (#571)', () => {
  it('bricht den Karten-Kopf um und haelt den Bearbeiten-Button auf dem Hit-Target aus AK 3', async () => {
    const linked = [playbook()]
    mockGetPersona.mockResolvedValue(personaContent())
    const { container } = renderCard(hookState({ playbooks: linked, linked }))

    // Gemessen bei 320 px: der Kopf misst 365 px in 286 px verfuegbarer
    // Breite, der Bearbeiten-Button lief 104 px ueber die Karten-Innenkante.
    const edit = await screen.findByRole('button', { name: 'Verknüpfungen bearbeiten' })
    expect(edit).toHaveClass('min-h-10')
    expect(edit).toHaveClass('md:min-h-0')

    const header = container.querySelector('.justify-between')
    expect(header).not.toBeNull()
    expect(header).toHaveClass('flex-wrap')

    const title = screen.getByRole('heading', { name: /Verknüpfte Playbooks/ })
    expect(title).toHaveClass('min-w-0')
    expect(title).toHaveClass('flex-wrap')
  })

  it('gibt dem Sub-Playbook-Namen eine Mindestbreite und der Zeile das Hit-Target aus AK 3', async () => {
    // Composite mit einem Kind: die Sub-Playbook-Zeile ist eine klickbare
    // Zeile mit Nummernchip, Name und Status-Badge. Gemessen bei 320 px blieben
    // dem Namen 81 px von 329 px Textbreite — `truncate` schnitt nach rund
    // acht Zeichen ab (AK 5). Mit `min-w-40` bricht der Badge um und der Name
    // behaelt 178 px; `min-h-10` hebt die 36 px hohe Zeile unterhalb `md` an.
    const child = playbook({ id: 'pb-child', name: 'Kind-Playbook' })
    const parent = playbook({
      id: 'pb1',
      is_composite: true,
      compose_children: [{ id: 'pb-child', name: 'Kind-Playbook' }],
    } as Partial<Playbook>)
    mockGetPersona.mockResolvedValue(personaContent())
    renderCard(hookState({ playbooks: [parent, child], linked: [parent] }))

    fireEvent.click(await screen.findByRole('button', { name: /Sub-Playbook/ }))

    const childLink = screen.getByRole('link', { name: /Kind-Playbook/ })
    expect(childLink).toHaveClass('min-h-10')
    expect(childLink).toHaveClass('md:min-h-0')
    expect(childLink).toHaveClass('flex-wrap')

    const name = childLink.querySelector('.truncate')
    expect(name).not.toBeNull()
    expect(name).toHaveTextContent('Kind-Playbook')
    expect(name).toHaveClass('min-w-40')
  })
})
