import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { EntityDuplicateButton } from './EntityDuplicateButton'

const onDuplicate = vi.fn()
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
  success: 'Persona dupliziert.',
  error: 'Duplizieren fehlgeschlagen.',
  viewerReadOnly: 'Viewer können Personae nur ansehen',
}

function renderButton() {
  return render(
    <EntityDuplicateButton
      texts={texts}
      label="Duplizieren"
      onDuplicate={onDuplicate}
      detailPath={(id) => `/w/ws-1/personas/${id}`}
      testId="duplicate-persona"
    />,
  )
}

beforeEach(() => {
  onDuplicate.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('EntityDuplicateButton', () => {
  it('dupliziert, toastet und navigiert zur Kopie', async () => {
    onDuplicate.mockResolvedValue({ id: 'p-2' })
    renderButton()

    fireEvent.click(screen.getByTestId('duplicate-persona'))

    await waitFor(() => {
      expect(onDuplicate).toHaveBeenCalledTimes(1)
      expect(notifySuccess).toHaveBeenCalledWith('Persona dupliziert.')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/personas/p-2')
    })
  })

  it('toastet den Fehler und navigiert nicht, wenn die Mutation scheitert', async () => {
    onDuplicate.mockRejectedValue(new Error('Kopie kaputt'))
    renderButton()

    fireEvent.click(screen.getByTestId('duplicate-persona'))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Kopie kaputt')
    })
    expect(navigate).not.toHaveBeenCalled()
    // Fehlerpfad gibt den Button wieder frei.
    expect(screen.getByTestId('duplicate-persona')).toBeEnabled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    renderButton()
    const button = screen.getByTestId('duplicate-persona')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', texts.viewerReadOnly)
  })
})
