// PlaceholderPreviewDialog.test.tsx — Event-getriebenes Preview-Overlay.
// Wir mocken useApi.previewPlaceholder und feuern das `placeholder-click`-
// CustomEvent auf dem Container; der Dialog soll oeffnen und den Output zeigen.
import { useRef } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PlaceholderPreviewDialog } from './PlaceholderPreviewDialog'
import {
  PLACEHOLDER_CLICK_EVENT,
  type PlaceholderClickDetail,
} from './PlaceholderBlock'

const previewPlaceholder = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ previewPlaceholder }),
}))

// Host-Komponente: stellt den Container-Ref bereit und gibt einen Button zum
// Dispatchen des Events frei (simuliert den Pill-Klick im bn-container).
function Host({ detail }: { detail: PlaceholderClickDetail }) {
  const ref = useRef<HTMLDivElement>(null)
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
      <PlaceholderPreviewDialog containerRef={ref} />
    </div>
  )
}

beforeEach(() => {
  previewPlaceholder.mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('PlaceholderPreviewDialog', () => {
  it('oeffnet bei placeholder-click und zeigt den aufgeloesten Output', async () => {
    previewPlaceholder.mockResolvedValue({
      kind: 'date',
      target_id: 'human',
      text: '1. Juni 2026',
      unresolved: false,
    })

    render(
      <Host detail={{ kind: 'date', target_id: 'human', label: 'Datum (lesbar)' }} />,
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
      <Host detail={{ kind: 'persona-field', target_id: 'name', label: 'Persona: Name' }} />,
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
      <Host detail={{ kind: 'playbook', target_id: 'x', label: 'Playbook: X' }} />,
    )
    fireEvent.click(screen.getByTestId('fire'))

    await waitFor(() => {
      expect(screen.getByTestId('placeholder-preview-error')).toBeInTheDocument()
    })
  })
})
