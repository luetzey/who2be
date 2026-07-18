import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ProvenanceEntry, VersionDiff } from '@/api/types'

import { VersionHistory, type VersionHistoryItem } from './VersionHistory'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const VERSIONS: VersionHistoryItem[] = [
  { version: 2, status: 'active', created_at: '2026-06-01T10:00:00Z' },
  { version: 1, status: 'inactive', created_at: '2026-05-01T10:00:00Z' },
]

function renderHistory(overrides: Partial<Parameters<typeof VersionHistory>[0]> = {}) {
  const diff: VersionDiff = {
    version: 1,
    against: 'active',
    against_version: 2,
    identical: false,
    changes: [{ path: 'description', op: 'changed', before: 'old', after: 'new' }],
  }
  const provenance: ProvenanceEntry[] = [
    {
      id: 'h1',
      entity_type: 'playbook',
      entity_id: 'p1',
      version: 2,
      from_status: 'review',
      to_status: 'active',
      changed_by: 'u1',
      changed_at: '2026-06-01T10:00:00Z',
      note: null,
    },
  ]
  const props = {
    versions: VERSIONS,
    canEdit: true,
    onRestore: vi.fn().mockResolvedValue(undefined),
    loadDiff: vi.fn().mockResolvedValue(diff),
    loadProvenance: vi.fn().mockResolvedValue(provenance),
    ...overrides,
  }
  render(<VersionHistory {...props} />)
  return props
}

describe('VersionHistory', () => {
  it('rendert alle Versionen mit Status-Badge', () => {
    renderHistory()
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
  })

  it('laedt und zeigt den Diff beim Klick', async () => {
    const props = renderHistory()
    fireEvent.click(screen.getAllByRole('button', { name: 'Diff' })[0])
    await waitFor(() => expect(props.loadDiff).toHaveBeenCalledWith(2))
    expect(await screen.findByText('description')).toBeInTheDocument()
    expect(screen.getByText('Geändert')).toBeInTheDocument()
  })

  it('beschriftet die Provenance der aktiven Version mit "Warum aktiv?"', async () => {
    const props = renderHistory()
    fireEvent.click(screen.getByRole('button', { name: 'Warum aktiv?' }))
    await waitFor(() => expect(props.loadProvenance).toHaveBeenCalledWith(2))
    expect(await screen.findByLabelText('Status-Historie')).toBeInTheDocument()
  })

  it('ruft onRestore beim Wiederherstellen ohne offenen Draft', async () => {
    const props = renderHistory()
    const buttons = screen.getAllByRole('button', { name: 'Wiederherstellen' })
    expect(buttons[0]).not.toBeDisabled()
    fireEvent.click(buttons[1])
    await waitFor(() => expect(props.onRestore).toHaveBeenCalledWith(1))
  })

  it('sperrt Wiederherstellen, wenn bereits ein Draft offen ist', () => {
    renderHistory({
      versions: [
        { version: 3, status: 'draft', created_at: '2026-06-02T10:00:00Z' },
        { version: 2, status: 'active', created_at: '2026-06-01T10:00:00Z' },
      ],
    })
    for (const button of screen.getAllByRole('button', { name: 'Wiederherstellen' })) {
      expect(button).toBeDisabled()
    }
  })

  it('blendet Wiederherstellen fuer Viewer aus', () => {
    renderHistory({ canEdit: false })
    expect(screen.queryByRole('button', { name: 'Wiederherstellen' })).not.toBeInTheDocument()
  })

  it('blendet den Diff-Button aus, wenn loadDiff fehlt (Entities ohne Diff-Endpoint)', () => {
    renderHistory({ loadDiff: undefined })
    expect(screen.queryByRole('button', { name: 'Diff' })).not.toBeInTheDocument()
    // Provenance bleibt unberuehrt.
    expect(screen.getByRole('button', { name: 'Warum aktiv?' })).toBeInTheDocument()
  })
})
