import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'
import { axe } from '@/test/a11y'

import { PlaybookComposesPicker } from './PlaybookComposesPicker'

// WICHTIG: Stabile Objekt-Referenz — kein frisches Objekt pro Render,
// sonst Render-Endlosschleife durch useEffect-Dep-Trigger → CI-Timeout.
const listPlaybooksMock = vi.fn()
const stableApi = { listPlaybooks: listPlaybooksMock }

vi.mock('@/api/useApi', () => ({
  useApi: () => stableApi,
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

describe('PlaybookComposesPicker (a11y)', () => {
  it('hat keine axe-Violations im geschlossenen Zustand (Trigger-Button)', async () => {
    listPlaybooksMock.mockResolvedValue([pbA, pbB])

    const { container } = render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations im geoeffneten Dialog', async () => {
    listPlaybooksMock.mockResolvedValue([pbA, pbB])

    const { container } = render(
      <PlaybookComposesPicker
        currentPlaybookId={currentId}
        existing={[pbA]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))

    // Warten bis Dialog-Inhalt geladen ist (axe sieht den Dialog-Content).
    await waitFor(() => {
      expect(screen.getByText('Atomic B')).toBeInTheDocument()
    })

    expect(await axe(container)).toHaveNoViolations()
  })
})
