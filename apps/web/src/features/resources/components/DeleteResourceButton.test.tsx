import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Resource } from '@/api/types'

import { DeleteResourceButton } from './DeleteResourceButton'

const deleteResource = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role = 'editor'

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ deleteResource }),
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
  deleteResource.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('DeleteResourceButton', () => {
  it('löscht nach Bestätigung und navigiert zur Liste', async () => {
    deleteResource.mockResolvedValue(undefined)
    render(<DeleteResourceButton resource={makeResource()} />)

    fireEvent.click(screen.getByTestId('delete-resource-trigger'))
    fireEvent.click(await screen.findByTestId('delete-resource-confirm'))

    await waitFor(() => {
      expect(deleteResource).toHaveBeenCalledWith('r-1')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/resources')
    })
  })

  it('zeigt bei 409 eine generische Blockier-Meldung ohne Liste', async () => {
    deleteResource.mockRejectedValue(new ApiError(409, 'Wird noch verwendet', {}))
    render(<DeleteResourceButton resource={makeResource()} />)

    fireEvent.click(screen.getByTestId('delete-resource-trigger'))
    fireEvent.click(await screen.findByTestId('delete-resource-confirm'))

    // Ohne Verwender-Liste fällt das Handling auf den generischen Fehler-Toast
    // zurück (kein Crash, kein blindes Retry).
    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Wird noch verwendet')
    })
    expect(navigate).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DeleteResourceButton resource={makeResource()} />)
    expect(screen.getByTestId('delete-resource-trigger')).toBeDisabled()
  })
})
