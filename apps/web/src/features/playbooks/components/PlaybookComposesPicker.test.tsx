import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'

import { PlaybookComposesPicker } from './PlaybookComposesPicker'

// Delay-freier Mock — sofortige Aufloesung wie in bestehenden Tests.
const listPlaybooksMock = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    listPlaybooks: listPlaybooksMock,
  }),
}))

const makePlaybook = (id: string, name: string): Playbook => ({
  id,
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name,
  current_version: 1,
  type: 'workflow',
  tags: [],
  triggers: null,
  content: {
    description: `Beschreibung von ${name}`,
    body: '',
    type: 'workflow',
    tags: [],
    triggers: null,
  },
  created_at: 't',
  updated_at: 't',
})

const pbA = makePlaybook('pb-a', 'Atomic A')
const pbB = makePlaybook('pb-b', 'Atomic B')
const currentId = 'pb-current'

describe('PlaybookComposesPicker', () => {
  it('oeffnet den Dialog und zeigt Workspace-Playbooks', async () => {
    listPlaybooksMock.mockResolvedValue([pbA, pbB])

    render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))

    await waitFor(() => {
      expect(screen.getByText('Atomic A')).toBeInTheDocument()
    })
    expect(screen.getByText('Atomic B')).toBeInTheDocument()
  })

  it('schliesst das aktuelle Playbook aus der Liste aus', async () => {
    const current = makePlaybook(currentId, 'Current Self')
    listPlaybooksMock.mockResolvedValue([current, pbA])

    render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))

    await waitFor(() => {
      expect(screen.getByText('Atomic A')).toBeInTheDocument()
    })
    // Das aktuelle Playbook darf nicht erscheinen.
    expect(screen.queryByText('Current Self')).not.toBeInTheDocument()
  })

  it('zeigt bestehende Kinder in der Ausgewaehlt-Liste', async () => {
    listPlaybooksMock.mockResolvedValue([pbA, pbB])

    render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[pbA]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))

    await waitFor(() => {
      const selectedList = screen.getByRole('list', {
        name: 'Ausgewaehlte Sub-Playbooks',
      })
      expect(selectedList).toHaveTextContent('Atomic A')
    })
    // pbA ist ausgewaehlt — darf nicht mehr in "Verfuegbare" stehen.
    const availableList = screen.getByRole('list', { name: 'Verfuegbare Playbooks' })
    expect(availableList).not.toHaveTextContent('Atomic A')
  })

  it('ruft onSave mit den ausgewaehlten IDs auf', async () => {
    listPlaybooksMock.mockResolvedValue([pbA, pbB])
    const onSave = vi.fn()

    render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[]}
        saving={false}
        onSave={onSave}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))

    // pbA auswaehlen.
    await waitFor(() => {
      expect(screen.getByText('Atomic A')).toBeInTheDocument()
    })
    fireEvent.click(
      screen.getByRole('checkbox', { name: 'Atomic A als Sub-Playbook hinzufügen' }),
    )

    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1)
    })
    expect(onSave).toHaveBeenCalledWith(['pb-a'])
  })

  it('unterstuetzt Up/Down-Reorder bestehender Kinder', async () => {
    listPlaybooksMock.mockResolvedValue([pbA, pbB])
    const onSave = vi.fn()

    render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[pbA, pbB]}
        saving={false}
        onSave={onSave}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))

    await waitFor(() => {
      expect(screen.getByRole('list', { name: 'Ausgewaehlte Sub-Playbooks' })).toBeInTheDocument()
    })

    // B ist an Position 2 — einmal nach oben.
    fireEvent.click(screen.getByRole('button', { name: 'Atomic B nach oben verschieben' }))

    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(['pb-b', 'pb-a'])
    })
  })
})
