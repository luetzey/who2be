import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Resource } from '@/api/types'

import { ExportResourceButton } from './ExportResourceButton'

const exportResource = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ exportResource }),
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

function makeResource(overrides: Partial<Resource> = {}): Resource {
  return {
    id: 'r-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Glossar',
    current_version: 1,
    content: { blocks: [] },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Resource
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
  exportResource.mockReset()
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

describe('ExportResourceButton', () => {
  it('exportiert als JSON und löst einen Download-Anchor aus', async () => {
    exportResource.mockResolvedValue({ id: 'r-1', name: 'Glossar' })
    render(<ExportResourceButton resource={makeResource()} />)

    fireEvent.keyDown(screen.getByTestId('export-resource-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-resource-json'))

    await waitFor(() => {
      expect(exportResource).toHaveBeenCalledWith('r-1', 'json')
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(createdAnchors.at(-1)?.download).toBe('who2be-resource-glossar.json')
  })
})
