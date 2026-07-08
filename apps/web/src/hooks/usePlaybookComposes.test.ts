import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { Playbook, PlaybookRef } from '@/api/types'
import { notify } from '@/lib/feedback'

import { usePlaybookComposes } from './usePlaybookComposes'

// Stabile api-Referenz — `api` steht in den useCallback-Deps des Hooks; eine
// frische Referenz pro Render wuerde den Load-Effect endlos neu feuern
// (Muster wie PlaybookComposesPicker.test.tsx).
const listPlaybookComposesMock = vi.fn()
const listPlaybookComposedByMock = vi.fn()
const setPlaybookComposesMock = vi.fn()
const stableApi = {
  listPlaybookComposes: listPlaybookComposesMock,
  listPlaybookComposedBy: listPlaybookComposedByMock,
  setPlaybookComposes: setPlaybookComposesMock,
}

vi.mock('@/api/useApi', () => ({
  useApi: () => stableApi,
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const child = { id: 'pb-child', name: 'Kind' } as Playbook
const parent: PlaybookRef = { id: 'pb-parent', name: 'Eltern' }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('usePlaybookComposes', () => {
  it('laedt Kinder und Backlinks im Happy-Path', async () => {
    listPlaybookComposesMock.mockResolvedValue([child])
    listPlaybookComposedByMock.mockResolvedValue([parent])

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))
    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.children).toEqual([child])
    expect(result.current.parents).toEqual([parent])
    expect(result.current.error).toBeNull()
  })

  it('laedt nichts ohne playbookId und startet nicht im Loading-Zustand', () => {
    const { result } = renderHook(() => usePlaybookComposes(undefined))

    expect(result.current.loading).toBe(false)
    expect(listPlaybookComposesMock).not.toHaveBeenCalled()
    expect(listPlaybookComposedByMock).not.toHaveBeenCalled()
  })

  it('behandelt 404 beider Endpoints als leere Listen statt Fehler', async () => {
    listPlaybookComposesMock.mockRejectedValue(new ApiError(404, 'not found'))
    listPlaybookComposedByMock.mockRejectedValue(new ApiError(404, 'not found'))

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.children).toEqual([])
    expect(result.current.parents).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('setzt error bei einem Nicht-404-ApiError', async () => {
    listPlaybookComposesMock.mockRejectedValue(new ApiError(500, 'Serverfehler'))
    listPlaybookComposedByMock.mockResolvedValue([])

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))

    await waitFor(() => {
      expect(result.current.error).toBe('Serverfehler')
    })
    expect(result.current.loading).toBe(false)
  })

  it('setzt einen generischen Fehlertext bei Nicht-Error-Rejections', async () => {
    listPlaybookComposesMock.mockResolvedValue([])
    listPlaybookComposedByMock.mockRejectedValue('kaputt')

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))

    await waitFor(() => {
      expect(result.current.error).toBe('Unbekannter Fehler.')
    })
  })

  it('ersetzt die Kinder-Liste beim Speichern und meldet Erfolg', async () => {
    listPlaybookComposesMock.mockResolvedValue([])
    listPlaybookComposedByMock.mockResolvedValue([])
    setPlaybookComposesMock.mockResolvedValue([child])

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save(['pb-child'])
    })

    expect(setPlaybookComposesMock).toHaveBeenCalledWith('pb-1', ['pb-child'])
    expect(result.current.children).toEqual([child])
    expect(result.current.saving).toBe(false)
    expect(notify.success).toHaveBeenCalledWith('Composition gespeichert.')
  })

  it('speichert nichts ohne playbookId', async () => {
    const { result } = renderHook(() => usePlaybookComposes(undefined))

    await act(async () => {
      await result.current.save(['pb-child'])
    })

    expect(setPlaybookComposesMock).not.toHaveBeenCalled()
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('meldet einen Zyklus-Fehler bei 409', async () => {
    listPlaybookComposesMock.mockResolvedValue([])
    listPlaybookComposedByMock.mockResolvedValue([])
    setPlaybookComposesMock.mockRejectedValue(new ApiError(409, 'conflict'))

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save(['pb-child'])
    })

    expect(notify.error).toHaveBeenCalledWith(
      'Verknuepfung wurde abgelehnt: Zyklus wuerde entstehen.',
    )
    expect(result.current.saving).toBe(false)
  })

  it('meldet die Fehlermeldung bei sonstigen Save-Fehlern', async () => {
    listPlaybookComposesMock.mockResolvedValue([])
    listPlaybookComposedByMock.mockResolvedValue([])
    setPlaybookComposesMock.mockRejectedValue(new ApiError(500, 'Speichern fehlgeschlagen'))

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save(['pb-child'])
    })

    expect(notify.error).toHaveBeenCalledWith('Speichern fehlgeschlagen')
  })

  it('meldet einen generischen Text bei Nicht-Error-Save-Rejections', async () => {
    listPlaybookComposesMock.mockResolvedValue([])
    listPlaybookComposedByMock.mockResolvedValue([])
    setPlaybookComposesMock.mockRejectedValue('kaputt')

    const { result } = renderHook(() => usePlaybookComposes('pb-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save(['pb-child'])
    })

    expect(notify.error).toHaveBeenCalledWith('Unbekannter Fehler.')
  })
})
