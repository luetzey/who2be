// PlaceholderPreviewPopover.test.tsx — Event-getriebenes, schwebendes Preview-
// Popover + Edit-Einstieg. Wir mocken useApi.previewPlaceholder und feuern das
// `placeholder-click`-CustomEvent auf dem Container; das Popover oeffnet sich
// und zeigt den Output.
import { useRef } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { type Measurable } from '@/components/ui/popover'

import { PlaceholderPreviewPopover } from './PlaceholderPreviewPopover'
import {
  PLACEHOLDER_CLICK_EVENT,
  type PlaceholderClickDetail,
} from './PlaceholderBlock'

const previewPlaceholder = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ previewPlaceholder }),
}))

// Baut ein vollstaendiges Detail inkl. `updateInlineContent`-Stub.
function makeDetail(
  partial: Omit<PlaceholderClickDetail, 'updateInlineContent'>,
): PlaceholderClickDetail {
  return { ...partial, updateInlineContent: vi.fn() }
}

// Host-Komponente: stellt den Container-Ref bereit und gibt einen Button zum
// Dispatchen des Events frei (simuliert den Pill-Klick im bn-container).
function Host({
  detail,
  editable = false,
  onEdit,
}: {
  detail: PlaceholderClickDetail
  editable?: boolean
  onEdit?: (detail: PlaceholderClickDetail) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const anchorRef = useRef<Measurable | null>(null)
  return (
    <div>
      <div ref={ref} data-testid="container">
        <button
          type="button"
          data-testid="fire"
          onClick={() =>
            ref.current?.dispatchEvent(
              new CustomEvent<PlaceholderClickDetail>(PLACEHOLDER_CLICK_EVENT, {
                detail,
                bubbles: true,
              }),
            )
          }
        >
          fire
        </button>
      </div>
      <PlaceholderPreviewPopover
        containerRef={ref}
        anchorRef={anchorRef}
        editable={editable}
        onEdit={onEdit}
      />
    </div>
  )
}

beforeEach(() => {
  previewPlaceholder.mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('PlaceholderPreviewPopover', () => {
  it('oeffnet bei placeholder-click und zeigt den aufgeloesten Output', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'date',
      target_id: 'human',
      text: '1. Juni 2026',
      unresolved: false,
    })

    render(
      <Host detail={makeDetail({ kind: 'date', target_id: 'human', label: 'Datum (lesbar)' })} />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-text')).toHaveTextContent('1. Juni 2026')
    })
    expect(previewPlaceholder).toHaveBeenCalledWith({ kind: 'date', target_id: 'human' })
    expect(screen.getByText('Datum (lesbar)')).toBeInTheDocument()
  })

  it('zeigt einen Hinweis statt Output, wenn der Platzhalter unresolved ist', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'persona-field',
      target_id: 'name',
      text: '',
      unresolved: true,
    })

    render(
      <Host detail={makeDetail({ kind: 'persona-field', target_id: 'name', label: 'Persona: Name' })} />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-miss')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('placeholder-preview-text')).not.toBeInTheDocument()
  })

  it('zeigt eine Fehlermeldung, wenn der Preview-Call fehlschlaegt', async () => {
    previewPlaceholder.mockRejectedValue(new Error('boom'))

    render(
      <Host detail={makeDetail({ kind: 'playbook', target_id: 'x', label: 'Playbook: X' })} />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      // ErrorAlert rendert role="alert" mit der Fehlermeldung.
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Vorschau konnte nicht geladen werden.',
      )
    })
  })

  it('kein "Bearbeiten" wenn nicht editierbar', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'playbook',
      target_id: 'pb1',
      text: 'Body',
      unresolved: false,
    })

    render(
      <Host detail={makeDetail({ kind: 'playbook', target_id: 'pb1', label: 'Playbook: X' })} />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-text')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('placeholder-preview-edit')).not.toBeInTheDocument()
  })

  it('kein "Bearbeiten" fuer tools-overview (parameterlos)', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'tools-overview',
      target_id: '',
      text: '## Werkzeuge',
      unresolved: false,
    })

    render(
      <Host
        editable
        detail={makeDetail({ kind: 'tools-overview', target_id: '', label: 'MCP-Tools' })}
      />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-text')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('placeholder-preview-edit')).not.toBeInTheDocument()
  })

  it('kein "Bearbeiten" fuer memory (parameterlos)', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'memory',
      target_id: '',
      text: 'Dieser Agent hat Zugriff auf kuratiertes Langzeitgedaechtnis.',
      unresolved: false,
    })

    render(
      <Host
        editable
        detail={makeDetail({ kind: 'memory', target_id: '', label: 'Gedächtnis-Hinweis' })}
      />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-text')).toBeInTheDocument()
    })
    expect(previewPlaceholder).toHaveBeenCalledWith({ kind: 'memory', target_id: '' })
    expect(screen.queryByTestId('placeholder-preview-edit')).not.toBeInTheDocument()
  })

  it('zeigt den aufgeloesten Tool-Ref-Output und bietet "Bearbeiten" (parametergebunden)', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'tool-ref',
      target_id: 'todo',
      text: 'Fähigkeit "todo" → Todoist.',
      unresolved: false,
    })

    render(
      <Host
        editable
        detail={makeDetail({ kind: 'tool-ref', target_id: 'todo', label: 'Tool: Todoist' })}
      />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-text')).toHaveTextContent(
        'Fähigkeit "todo" → Todoist.',
      )
    })
    expect(previewPlaceholder).toHaveBeenCalledWith({ kind: 'tool-ref', target_id: 'todo' })
    // Anders als tools-overview/persona-ref ist tool-ref parametergebunden
    // (target_id = Alias) — der Bearbeiten-Button muss verfuegbar sein.
    expect(screen.getByTestId('placeholder-preview-edit')).toBeInTheDocument()
  })

  it('zeigt einen Miss-Hinweis fuer einen nicht gebundenen Tool-Ref-Alias', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'tool-ref',
      target_id: 'unbekannt',
      text: '',
      unresolved: true,
    })

    render(
      <Host
        detail={makeDetail({ kind: 'tool-ref', target_id: 'unbekannt', label: 'Tool: unbekannt' })}
      />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-miss')).toBeInTheDocument()
    })
  })

  it('editierbar: "Bearbeiten" ruft onEdit mit dem Detail (inkl. updateInlineContent)', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'playbook',
      target_id: 'pb1',
      text: 'Body',
      unresolved: false,
    })
    const onEdit = vi.fn()
    const detail = makeDetail({ kind: 'playbook', target_id: 'pb1', label: 'Playbook: X' })

    render(<Host editable detail={detail} onEdit={onEdit} />)
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-edit')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('placeholder-preview-edit'))

    expect(onEdit).toHaveBeenCalledWith(detail)
    // Overlay schliesst nach dem Edit-Start.
    await waitFor(() => {
      expect(screen.queryByTestId('placeholder-preview-popover')).not.toBeInTheDocument()
    })
  })
})
