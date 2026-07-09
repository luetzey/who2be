import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import type { ResourceRef, SubResource, SubResourceLinkInput } from '@/api/types'
import { notify } from '@/lib/feedback'

import { useResourceSubResources } from './useResourceSubResources'

// Stabile api-Referenz — `api` steht in den useCallback-Deps des Hooks; eine
// frische Referenz pro Render wuerde den Load-Effect endlos neu feuern
// (Muster wie PlaybookComposesPicker.test.tsx).
const listResourceSubResourcesMock = vi.fn()
const listResourceUsedByMock = vi.fn()
const setResourceSubResourcesMock = vi.fn()
const stableApi = {
  listResourceSubResources: listResourceSubResourcesMock,
  listResourceUsedBy: listResourceUsedByMock,
  setResourceSubResources: setResourceSubResourcesMock,
}

vi.mock('@/api/useApi', () => ({
  useApi: () => stableApi,
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const child: SubResource = {
  id: 'res-child',
  name: 'Kind-Resource',
  link_scope: 'resource',
  block_id: null,
  position: 0,
  fetch_call: 'fetch_resource(res-child)',
}
const parent: ResourceRef = { id: 'res-parent', name: 'Eltern-Resource' }
const linkInput: SubResourceLinkInput = {
  child_id: 'res-child',
  block_id: null,
  position: 0,
  link_scope: 'resource',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useResourceSubResources', () => {
  it('laedt Kinder und Backlinks im Happy-Path', async () => {
    listResourceSubResourcesMock.mockResolvedValue([child])
    listResourceUsedByMock.mockResolvedValue([parent])

    const { result } = renderHook(() => useResourceSubResources('res-1'))
    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.children).toEqual([child])
    expect(result.current.parents).toEqual([parent])
    expect(result.current.error).toBeNull()
  })

  it('laedt nichts ohne resourceId und startet nicht im Loading-Zustand', () => {
    const { result } = renderHook(() => useResourceSubResources(undefined))

    expect(result.current.loading).toBe(false)
    expect(listResourceSubResourcesMock).not.toHaveBeenCalled()
    expect(listResourceUsedByMock).not.toHaveBeenCalled()
  })

  it('behandelt 404 beider Endpoints als leere Listen statt Fehler', async () => {
    listResourceSubResourcesMock.mockRejectedValue(new ApiError(404, 'not found'))
    listResourceUsedByMock.mockRejectedValue(new ApiError(404, 'not found'))

    const { result } = renderHook(() => useResourceSubResources('res-1'))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.children).toEqual([])
    expect(result.current.parents).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('setzt error bei einem Nicht-404-ApiError', async () => {
    listResourceSubResourcesMock.mockRejectedValue(new ApiError(500, 'Serverfehler'))
    listResourceUsedByMock.mockResolvedValue([])

    const { result } = renderHook(() => useResourceSubResources('res-1'))

    await waitFor(() => {
      expect(result.current.error).toBe('Serverfehler')
    })
    expect(result.current.loading).toBe(false)
  })

  it('setzt einen generischen Fehlertext bei Nicht-Error-Rejections', async () => {
    listResourceSubResourcesMock.mockResolvedValue([])
    listResourceUsedByMock.mockRejectedValue('kaputt')

    const { result } = renderHook(() => useResourceSubResources('res-1'))

    await waitFor(() => {
      expect(result.current.error).toBe('Unbekannter Fehler.')
    })
  })

  it('ersetzt die Kinder-Liste beim Speichern und meldet Erfolg', async () => {
    listResourceSubResourcesMock.mockResolvedValue([])
    listResourceUsedByMock.mockResolvedValue([])
    setResourceSubResourcesMock.mockResolvedValue([child])

    const { result } = renderHook(() => useResourceSubResources('res-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save([linkInput])
    })

    expect(setResourceSubResourcesMock).toHaveBeenCalledWith('res-1', [linkInput])
    expect(result.current.children).toEqual([child])
    expect(result.current.saving).toBe(false)
    expect(notify.success).toHaveBeenCalledWith('Sub-Resources gespeichert.')
  })

  it('speichert nichts ohne resourceId', async () => {
    const { result } = renderHook(() => useResourceSubResources(undefined))

    await act(async () => {
      await result.current.save([linkInput])
    })

    expect(setResourceSubResourcesMock).not.toHaveBeenCalled()
    expect(notify.success).not.toHaveBeenCalled()
  })

  it('meldet einen Zyklus-Fehler bei 409', async () => {
    listResourceSubResourcesMock.mockResolvedValue([])
    listResourceUsedByMock.mockResolvedValue([])
    setResourceSubResourcesMock.mockRejectedValue(new ApiError(409, 'conflict'))

    const { result } = renderHook(() => useResourceSubResources('res-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save([linkInput])
    })

    expect(notify.error).toHaveBeenCalledWith(
      'Verknuepfung wurde abgelehnt: Zyklus wuerde entstehen.',
    )
    expect(result.current.saving).toBe(false)
  })

  it('meldet die Fehlermeldung bei sonstigen Save-Fehlern', async () => {
    listResourceSubResourcesMock.mockResolvedValue([])
    listResourceUsedByMock.mockResolvedValue([])
    setResourceSubResourcesMock.mockRejectedValue(new ApiError(500, 'Speichern fehlgeschlagen'))

    const { result } = renderHook(() => useResourceSubResources('res-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save([linkInput])
    })

    expect(notify.error).toHaveBeenCalledWith('Speichern fehlgeschlagen')
  })

  it('meldet einen generischen Text bei Nicht-Error-Save-Rejections', async () => {
    listResourceSubResourcesMock.mockResolvedValue([])
    listResourceUsedByMock.mockResolvedValue([])
    setResourceSubResourcesMock.mockRejectedValue('kaputt')

    const { result } = renderHook(() => useResourceSubResources('res-1'))
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    await act(async () => {
      await result.current.save([linkInput])
    })

    expect(notify.error).toHaveBeenCalledWith('Unbekannter Fehler.')
  })
})
