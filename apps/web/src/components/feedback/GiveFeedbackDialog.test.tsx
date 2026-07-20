import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Button } from '@/components/ui/button'

import { GiveFeedbackDialog } from './GiveFeedbackDialog'

const { submitFeedback } = vi.hoisted(() => ({ submitFeedback: vi.fn() }))

vi.mock('@/api/useApi', () => ({ useApi: () => ({ submitFeedback }) }))
vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

beforeEach(() => {
  submitFeedback.mockReset()
  submitFeedback.mockResolvedValue(undefined)
})

describe('GiveFeedbackDialog', () => {
  it('sendet das gewählte Signal ohne Notiz (note bleibt undefined)', async () => {
    render(
      <GiveFeedbackDialog
        entityType="resource"
        entityId="r1"
        entityName="Onboarding"
        version={2}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Feedback geben' }))
    fireEvent.change(await screen.findByLabelText('Signal'), {
      target: { value: 'outdated' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Absenden' }))

    await waitFor(() =>
      expect(submitFeedback).toHaveBeenCalledWith({
        entity_type: 'resource',
        entity_id: 'r1',
        version: 2,
        signal: 'outdated',
        note: undefined,
      }),
    )
  })

  it('trimmt die Notiz und schickt den Default-Signal „helpful"', async () => {
    render(
      <GiveFeedbackDialog entityType="persona" entityId="p1" entityName="Coach" />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Feedback geben' }))
    fireEvent.change(await screen.findByLabelText('Notiz (optional)'), {
      target: { value: '  läuft rund  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Absenden' }))

    await waitFor(() =>
      expect(submitFeedback).toHaveBeenCalledWith({
        entity_type: 'persona',
        entity_id: 'p1',
        version: undefined,
        signal: 'helpful',
        note: 'läuft rund',
      }),
    )
  })

  it('rendert einen übergebenen Trigger statt des Default-Buttons', async () => {
    render(
      <GiveFeedbackDialog
        entityType="playbook"
        entityId="pb1"
        entityName="Reset-Flow"
        trigger={<Button>Bewerten</Button>}
      />,
    )

    expect(
      screen.queryByRole('button', { name: 'Feedback geben' }),
    ).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Bewerten' }))
    expect(await screen.findByLabelText('Signal')).toBeInTheDocument()
  })
})
