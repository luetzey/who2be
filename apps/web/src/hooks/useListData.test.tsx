import { act, render, screen, waitFor } from '@testing-library/react'
import { useCallback } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { useListData } from './useListData'

function Probe<T>({ loader }: { loader: () => Promise<T[]> }) {
  const stable = useCallback(loader, [loader])
  const { data, loading, error, reload } = useListData<T>(stable)
  return (
    <div>
      <p data-testid="loading">{loading ? 'yes' : 'no'}</p>
      <p data-testid="error">{error ?? '-'}</p>
      <p data-testid="count">{data.length}</p>
      <button type="button" onClick={reload}>
        reload
      </button>
    </div>
  )
}

describe('useListData', () => {
  it('liefert Daten und stoppt das Laden im Happy-Path', async () => {
    const loader = vi.fn().mockResolvedValue([1, 2, 3])

    render(<Probe loader={loader} />)

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('no')
    })
    expect(screen.getByTestId('count')).toHaveTextContent('3')
    expect(screen.getByTestId('error')).toHaveTextContent('-')
  })

  it('uebersetzt einen Fehler in den error-State', async () => {
    const loader = vi.fn().mockRejectedValue(new Error('offline'))

    render(<Probe loader={loader} />)

    await waitFor(() => {
      expect(screen.getByTestId('error')).toHaveTextContent('offline')
    })
    expect(screen.getByTestId('loading')).toHaveTextContent('no')
  })

  it('ruft den Loader erneut auf, wenn reload getriggert wird', async () => {
    const loader = vi.fn().mockResolvedValue([])

    render(<Probe loader={loader} />)

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('no')
    })
    expect(loader).toHaveBeenCalledTimes(1)

    await act(async () => {
      screen.getByRole('button', { name: 'reload' }).click()
    })

    expect(loader).toHaveBeenCalledTimes(2)
  })
})
