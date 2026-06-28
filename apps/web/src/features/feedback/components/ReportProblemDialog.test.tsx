import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ReportProblemDialog } from './ReportProblemDialog'

const { submitSystemFeedback } = vi.hoisted(() => ({ submitSystemFeedback: vi.fn() }))

vi.mock('@/api/useApi', () => ({ useApi: () => ({ submitSystemFeedback }) }))
vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

beforeEach(() => {
  submitSystemFeedback.mockResolvedValue(undefined)
})

describe('ReportProblemDialog', () => {
  it('meldet ein System-Problem mit Kategorie + Beschreibung', async () => {
    const onReported = vi.fn()
    render(<ReportProblemDialog onReported={onReported} />)

    fireEvent.click(screen.getByRole('button', { name: 'Problem melden' }))
    fireEvent.change(await screen.findByLabelText('Kategorie'), { target: { value: 'mcp' } })
    fireEvent.change(screen.getByLabelText('Beschreibung'), {
      target: { value: 'fetch_playbook liefert 500' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Melden' }))

    await waitFor(() =>
      expect(submitSystemFeedback).toHaveBeenCalledWith({
        category: 'mcp',
        note: 'fetch_playbook liefert 500',
      }),
    )
    await waitFor(() => expect(onReported).toHaveBeenCalled())
  })

  it('sperrt „Melden" ohne Beschreibung', async () => {
    render(<ReportProblemDialog />)
    fireEvent.click(screen.getByRole('button', { name: 'Problem melden' }))
    expect(await screen.findByRole('button', { name: 'Melden' })).toBeDisabled()
  })
})
