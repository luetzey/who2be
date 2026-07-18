import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ExternalTool } from '@/api/types'

import { ExportToolButton } from './ExportToolButton'

const exportExternalTool = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ exportExternalTool }),
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

function makeTool(overrides: Partial<ExternalTool> = {}): ExternalTool {
  return {
    id: 't-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Todoist',
    alias: 'todo',
    current_version: 1,
    content: {
      display_name: 'Todoist',
      mcp_server_name: 'Todoist MCP',
      tool_names: [],
      usage_notes: '[]',
      fallback_note: null,
      tags: [],
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as ExternalTool
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
  exportExternalTool.mockReset()
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

describe('ExportToolButton', () => {
  it('exportiert als JSON und löst einen Download-Anchor aus', async () => {
    exportExternalTool.mockResolvedValue({ id: 't-1', name: 'Todoist' })
    render(<ExportToolButton tool={makeTool()} />)

    fireEvent.keyDown(screen.getByTestId('export-tool-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-tool-json'))

    await waitFor(() => {
      expect(exportExternalTool).toHaveBeenCalledWith('t-1', 'json')
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(createdAnchors.at(-1)?.download).toBe('who2be-external-tool-todoist.json')
  })

  it('meldet einen Fehler per Toast, wenn der Export fehlschlaegt', async () => {
    exportExternalTool.mockRejectedValue(new Error('Export kaputt'))
    render(<ExportToolButton tool={makeTool()} />)

    fireEvent.keyDown(screen.getByTestId('export-tool-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-tool-markdown'))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Export kaputt')
    })
    expect(notifySuccess).not.toHaveBeenCalled()
  })
})
