import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'

import { PersonaPlaybooksCard } from './PersonaPlaybooksCard'

vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))
vi.mock('@/hooks/usePersonaPlaybooks', () => ({
  usePersonaPlaybooks: vi.fn(),
}))

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
  render(
    <MemoryRouter>
      <PersonaPlaybooksCard personaId="p1" canEdit={canEdit} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.mocked(usePersonaPlaybooks).mockReset()
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
