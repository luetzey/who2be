import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Persona } from '@/api/types'

import { DeletePersonaButton } from './DeletePersonaButton'

const deletePersona = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role = 'editor'

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ deletePersona }),
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
  deletePersona.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('DeletePersonaButton', () => {
  it('löscht nach Bestätigung und navigiert zur Liste', async () => {
    deletePersona.mockResolvedValue(undefined)
    render(<DeletePersonaButton persona={makePersona()} />)

    fireEvent.click(screen.getByTestId('delete-persona-trigger'))
    const confirm = await screen.findByTestId('delete-persona-confirm')
    fireEvent.click(confirm)

    await waitFor(() => {
      expect(deletePersona).toHaveBeenCalledWith('p-1')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/personas')
    })
  })

  it('zeigt bei 409 die blockierenden Verwender und navigiert nicht', async () => {
    deletePersona.mockRejectedValue(
      new ApiError(409, 'Who2Be-API-Fehler (409).', {
        detail: {
          message: 'Persona wird noch von Agenten verwendet.',
          blocked_by: { agents: [{ agent_id: 'a-1', agent_name: 'Agent Sam' }] },
        },
      }),
    )
    render(<DeletePersonaButton persona={makePersona()} />)

    fireEvent.click(screen.getByTestId('delete-persona-trigger'))
    fireEvent.click(await screen.findByTestId('delete-persona-confirm'))

    await waitFor(() => {
      expect(screen.getByText(/Agent Sam/)).toBeInTheDocument()
    })
    expect(navigate).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DeletePersonaButton persona={makePersona()} />)
    expect(screen.getByTestId('delete-persona-trigger')).toBeDisabled()
  })
})
