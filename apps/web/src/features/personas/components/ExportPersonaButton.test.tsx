import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Persona } from '@/api/types'

import { ExportPersonaButton } from './ExportPersonaButton'

const exportPersona = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ exportPersona }),
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

function makePersona(overrides: Partial<Persona> = {}): Persona {
  return {
    id: 'p-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Carla',
    current_version: 1,
    content: { description: '', system_prompt: '' },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Persona
}

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
  exportPersona.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  createdAnchors = []
  anchorClick = vi.fn()
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreate(tag)
    if (tag === 'a') {
      el.click = anchorClick
      createdAnchors.push(el as HTMLAnchorElement)
    }
    return el
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function openDropdown() {
  // Radix oeffnet auf pointerdown+up; in jsdom kommen wir per Enter ans Ziel.
  fireEvent.keyDown(screen.getByTestId('export-persona-trigger'), { key: 'Enter' })
}

describe('ExportPersonaButton', () => {
  it('exportiert als JSON und löst einen Download-Anchor aus', async () => {
    exportPersona.mockResolvedValue({ id: 'p-1', name: 'Carla' })
    render(<ExportPersonaButton persona={makePersona()} />)

    openDropdown()
    fireEvent.click(await screen.findByTestId('export-persona-json'))

    await waitFor(() => {
      expect(exportPersona).toHaveBeenCalledWith('p-1', 'json')
      expect(anchorClick).toHaveBeenCalled()
    })
    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-persona-carla.json')
  })

  it('exportiert als Markdown mit dem korrekten Format', async () => {
    exportPersona.mockResolvedValue('# Carla')
    render(<ExportPersonaButton persona={makePersona()} />)

    openDropdown()
    fireEvent.click(await screen.findByTestId('export-persona-markdown'))

    await waitFor(() => {
      expect(exportPersona).toHaveBeenCalledWith('p-1', 'markdown')
      expect(anchorClick).toHaveBeenCalled()
    })
    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-persona-carla.md')
  })
})
