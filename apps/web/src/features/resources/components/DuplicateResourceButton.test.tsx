import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Resource } from '@/api/types'

import { DuplicateResourceButton } from './DuplicateResourceButton'

const duplicateResource = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role = 'editor'

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ duplicateResource }),
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
    slug: 'glossar',
    current_version: 1,
    content: { blocks: [] },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Resource
}

beforeEach(() => {
  duplicateResource.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('DuplicateResourceButton', () => {
  it('dupliziert und navigiert zur Kopie', async () => {
    duplicateResource.mockResolvedValue(makeResource({ id: 'r-2', slug: 'glossar-kopie' }))
    render(<DuplicateResourceButton resource={makeResource()} />)

    fireEvent.click(screen.getByTestId('duplicate-resource'))

    await waitFor(() => {
      expect(duplicateResource).toHaveBeenCalledWith('r-1')
      expect(notifySuccess).toHaveBeenCalledWith('Resource dupliziert.')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/resources/r-2')
    })
  })

  it('meldet den Fehler per Toast, wenn das Duplizieren fehlschlägt', async () => {
    duplicateResource.mockRejectedValue(new ApiError(500, 'Serverfehler', {}))
    render(<DuplicateResourceButton resource={makeResource()} />)

    fireEvent.click(screen.getByTestId('duplicate-resource'))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Serverfehler')
    })
    expect(navigate).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DuplicateResourceButton resource={makeResource()} />)
    expect(screen.getByTestId('duplicate-resource')).toBeDisabled()
  })
})
