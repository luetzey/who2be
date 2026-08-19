import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { EntityExportButton } from './EntityExportButton'

const onExport = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

let anchorClick: ReturnType<typeof vi.fn>
let createdAnchors: HTMLAnchorElement[]

beforeAll(() => {
  for (const fn of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

beforeEach(() => {
  onExport.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  createdAnchors = []
  anchorClick = vi.fn()
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreate(tag)
    if (tag === 'a') {
      el.click = anchorClick as () => void
      createdAnchors.push(el as HTMLAnchorElement)
    }
    return el
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function renderButton() {
  return render(
    <EntityExportButton
      entityKind="persona"
      name="Carla"
      onExport={onExport}
      testIdPrefix="export-persona"
    />,
  )
}

function openDropdown() {
  // Radix oeffnet auf pointerdown+up; in jsdom kommen wir per Enter ans Ziel
  // (Muster der frueheren Export*Button-Tests).
  fireEvent.keyDown(screen.getByTestId('export-persona-trigger'), { key: 'Enter' })
}

describe('EntityExportButton', () => {
  it('exportiert als JSON und löst einen Download-Anchor aus', async () => {
    onExport.mockResolvedValue({ id: 'p-1', name: 'Carla' })
    renderButton()

    openDropdown()
    fireEvent.click(await screen.findByTestId('export-persona-json'))

    await waitFor(() => {
      expect(onExport).toHaveBeenCalledWith('json')
      expect(anchorClick).toHaveBeenCalled()
    })
    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-persona-carla.json')
  })

  it('exportiert als Markdown mit dem korrekten Format', async () => {
    onExport.mockResolvedValue('# Carla')
    renderButton()

    openDropdown()
    fireEvent.click(await screen.findByTestId('export-persona-markdown'))

    await waitFor(() => {
      expect(onExport).toHaveBeenCalledWith('markdown')
      expect(anchorClick).toHaveBeenCalled()
    })
    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-persona-carla.md')
  })

  it('toastet den Fehler, wenn der Export scheitert', async () => {
    onExport.mockRejectedValue(new Error('Export kaputt'))
    renderButton()

    openDropdown()
    fireEvent.click(await screen.findByTestId('export-persona-json'))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Export kaputt')
    })
    expect(anchorClick).not.toHaveBeenCalled()
  })
})
