import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Playbook } from '@/api/types'

import { DeletePlaybookButton } from './DeletePlaybookButton'

const deletePlaybook = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role = 'editor'

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ deletePlaybook }),
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

function makePlaybook(overrides: Partial<Playbook> = {}): Playbook {
  return {
    id: 'pb-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Onboarding',
    current_version: 1,
    type: 'guide',
    tags: [],
    triggers: null,
    content: { body: '' },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Playbook
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
  deletePlaybook.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('DeletePlaybookButton', () => {
  it('löscht nach Bestätigung und navigiert zur Liste', async () => {
    deletePlaybook.mockResolvedValue(undefined)
    render(<DeletePlaybookButton playbook={makePlaybook()} />)

    fireEvent.click(screen.getByTestId('delete-playbook-trigger'))
    fireEvent.click(await screen.findByTestId('delete-playbook-confirm'))

    await waitFor(() => {
      expect(deletePlaybook).toHaveBeenCalledWith('pb-1')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/playbooks')
    })
  })

  it('zeigt bei 409 die blockierenden Verwender (Personas + Composites)', async () => {
    deletePlaybook.mockRejectedValue(
      new ApiError(409, 'Who2Be-API-Fehler (409).', {
        detail: {
          message: 'Playbook wird noch verwendet.',
          blocked_by: {
            personas: [{ persona_id: 'per-1', persona_name: 'Persona Max' }],
            composites: [{ id: 'pb-9', name: 'Composite Playbook' }],
          },
        },
      }),
    )
    render(<DeletePlaybookButton playbook={makePlaybook()} />)

    fireEvent.click(screen.getByTestId('delete-playbook-trigger'))
    fireEvent.click(await screen.findByTestId('delete-playbook-confirm'))

    await waitFor(() => {
      expect(screen.getByText(/Persona Max/)).toBeInTheDocument()
    })
    expect(navigate).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DeletePlaybookButton playbook={makePlaybook()} />)
    expect(screen.getByTestId('delete-playbook-trigger')).toBeDisabled()
  })
})
