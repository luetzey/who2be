import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'

import { EntityDeleteButton } from './EntityDeleteButton'

const onDelete = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role = 'editor'

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
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

const texts = {
  dialogTitle: 'Persona löschen?',
  success: 'Persona gelöscht.',
  viewerReadOnly: 'Viewer können Personae nur ansehen',
  blockedMessage: 'Diese Persona wird noch verwendet von:',
}

function renderButton() {
  return render(
    <EntityDeleteButton
      name="Carla"
      texts={texts}
      onDelete={onDelete}
      listPath="/w/ws-1/personas"
      testIdPrefix="delete-persona"
    />,
  )
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
  onDelete.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('EntityDeleteButton', () => {
  it('löscht nach Bestätigung, toastet und navigiert zur Liste', async () => {
    onDelete.mockResolvedValue(undefined)
    renderButton()

    fireEvent.click(screen.getByTestId('delete-persona-trigger'))
    fireEvent.click(await screen.findByTestId('delete-persona-confirm'))

    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledTimes(1)
      expect(notifySuccess).toHaveBeenCalledWith('Persona gelöscht.')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/personas')
    })
  })

  it('zeigt bei 409 die blockierenden Verwender und navigiert nicht', async () => {
    onDelete.mockRejectedValue(
      new ApiError(409, 'Who2Be-API-Fehler (409).', {
        detail: {
          message: 'Persona wird noch von Agenten verwendet.',
          blocked_by: { agents: [{ agent_id: 'a-1', agent_name: 'Agent Sam' }] },
        },
      }),
    )
    renderButton()

    fireEvent.click(screen.getByTestId('delete-persona-trigger'))
    fireEvent.click(await screen.findByTestId('delete-persona-confirm'))

    await waitFor(() => {
      expect(screen.getByText(/Agent Sam/)).toBeInTheDocument()
    })
    expect(navigate).not.toHaveBeenCalled()
    // Blocker-Anzeige sperrt den Confirm-Button — kein blindes Retry.
    expect(screen.getByTestId('delete-persona-confirm')).toBeDisabled()
  })

  it('toastet den Fehler bei Nicht-409 und bleibt auf der Seite', async () => {
    onDelete.mockRejectedValue(new Error('Kaputt'))
    renderButton()

    fireEvent.click(screen.getByTestId('delete-persona-trigger'))
    fireEvent.click(await screen.findByTestId('delete-persona-confirm'))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Kaputt')
    })
    expect(navigate).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    renderButton()
    const trigger = screen.getByTestId('delete-persona-trigger')
    expect(trigger).toBeDisabled()
    expect(trigger).toHaveAttribute('title', texts.viewerReadOnly)
  })
})
