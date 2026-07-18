import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { ExternalTool } from '@/api/types'

import { DeleteToolButton } from './DeleteToolButton'

const deleteExternalTool = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role = 'editor'

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ deleteExternalTool }),
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
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
})

beforeEach(() => {
  deleteExternalTool.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('DeleteToolButton', () => {
  it('löscht nach Bestätigung und navigiert zur Liste', async () => {
    deleteExternalTool.mockResolvedValue(undefined)
    render(<DeleteToolButton tool={makeTool()} />)

    fireEvent.click(screen.getByTestId('delete-tool-trigger'))
    fireEvent.click(await screen.findByTestId('delete-tool-confirm'))

    await waitFor(() => {
      expect(deleteExternalTool).toHaveBeenCalledWith('t-1')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/tools')
    })
  })

  it('zeigt bei 409 eine generische Blockier-Meldung ohne Liste', async () => {
    deleteExternalTool.mockRejectedValue(new ApiError(409, 'Wird noch verwendet', {}))
    render(<DeleteToolButton tool={makeTool()} />)

    fireEvent.click(screen.getByTestId('delete-tool-trigger'))
    fireEvent.click(await screen.findByTestId('delete-tool-confirm'))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Wird noch verwendet')
    })
    expect(navigate).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DeleteToolButton tool={makeTool()} />)
    expect(screen.getByTestId('delete-tool-trigger')).toBeDisabled()
  })
})
