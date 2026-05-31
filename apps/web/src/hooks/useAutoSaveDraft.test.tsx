import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { useAutoSaveDraft } from './useAutoSaveDraft'

// useAutoSaveDraft testen wir bewusst mit einer winzigen Debounce-Konstante
// (50 ms), damit Real-Timer + waitFor schnell konvergieren. Die produktive
// Default-Debounce (1500 ms) ist durch die DetailPage-Integrationstests
// abgedeckt.

interface Values {
  name: string
}

function Harness({
  patchFn,
  initialName = '',
  isReady = true,
}: {
  patchFn: (values: Values) => Promise<void>
  initialName?: string
  isReady?: boolean
}) {
  const [name, setName] = useState(initialName)
  const result = useAutoSaveDraft<Values>({
    values: { name },
    isReady,
    patchFn,
    debounceMs: 50,
  })
  return (
    <div>
      <input
        aria-label="name"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <span data-testid="status">{result.status}</span>
      <span data-testid="error">{result.errorMessage ?? ''}</span>
      <button type="button" onClick={() => void result.flush()}>
        flush
      </button>
    </div>
  )
}

describe('useAutoSaveDraft', () => {
  it('debounced den PATCH-Call und faerbt den Status auf saved', async () => {
    const patchFn = vi.fn().mockResolvedValue(undefined)
    render(<Harness patchFn={patchFn} initialName="" />)

    fireEvent.change(screen.getByLabelText('name'), { target: { value: 'foo' } })

    // Real-Wait fuer Debounce + Flush.
    await new Promise<void>((resolve) => setTimeout(resolve, 200))

    expect(patchFn).toHaveBeenCalledTimes(1)
    expect(patchFn.mock.calls[0][0]).toEqual({ name: 'foo' })
    expect(screen.getByTestId('status').textContent).toBe('saved')
  })

  it('feuert keinen PATCH, wenn `isReady=false`', async () => {
    const patchFn = vi.fn().mockResolvedValue(undefined)
    render(<Harness patchFn={patchFn} isReady={false} initialName="seed" />)

    await new Promise<void>((resolve) => setTimeout(resolve, 120))
    expect(patchFn).not.toHaveBeenCalled()
  })

  it('serialisiert Werte und unterdrueckt PATCH bei unveraendertem Snapshot', async () => {
    const patchFn = vi.fn().mockResolvedValue(undefined)
    const { rerender } = render(<Harness patchFn={patchFn} initialName="x" />)
    await new Promise<void>((resolve) => setTimeout(resolve, 120))

    // Erneutes Rendern mit gleichem State darf keinen PATCH ausloesen.
    rerender(<Harness patchFn={patchFn} initialName="x" />)
    await new Promise<void>((resolve) => setTimeout(resolve, 120))
    expect(patchFn).not.toHaveBeenCalled()
  })

  it('faerbt Status auf error, wenn der PATCH fehlschlaegt', async () => {
    const patchFn = vi.fn().mockRejectedValue(new Error('boom'))
    render(<Harness patchFn={patchFn} />)

    fireEvent.change(screen.getByLabelText('name'), { target: { value: 'fail' } })
    await new Promise<void>((resolve) => setTimeout(resolve, 200))
    expect(screen.getByTestId('status').textContent).toBe('error')
    expect(screen.getByTestId('error').textContent).toBe('boom')
  })

  it('flush() feuert sofort und vor dem Debounce', async () => {
    const patchFn = vi.fn().mockResolvedValue(undefined)
    render(<Harness patchFn={patchFn} />)

    fireEvent.change(screen.getByLabelText('name'), { target: { value: 'now' } })

    const flushBtn = screen.getByRole('button', { name: 'flush' })
    await act(async () => {
      flushBtn.click()
      // Mehrere Microtasks fuer die verschachtelten Promise-Chains.
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(patchFn).toHaveBeenCalledTimes(1)
    expect(patchFn.mock.calls[0][0]).toEqual({ name: 'now' })
  })
})
