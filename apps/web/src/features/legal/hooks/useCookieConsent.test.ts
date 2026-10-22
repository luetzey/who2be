import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CONSENT_STORAGE_KEY, useCookieConsent } from './useCookieConsent'

afterEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('useCookieConsent', () => {
  it('startet unbestaetigt und speichert die Kenntnisnahme', () => {
    const { result } = renderHook(() => useCookieConsent())
    expect(result.current.isDecided).toBe(false)
    act(() => result.current.acknowledge())
    expect(result.current.isDecided).toBe(true)
    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBe('acknowledged')
  })

  it('meldet die Bestaetigung im selben Tab an andere Instanzen (Begruessung wartet darauf)', () => {
    const banner = renderHook(() => useCookieConsent())
    const waiter = renderHook(() => useCookieConsent())
    expect(waiter.result.current.isDecided).toBe(false)
    act(() => banner.result.current.acknowledge())
    expect(waiter.result.current.isDecided).toBe(true)
  })

  it('kommt auch ohne Storage im selben Tab an (Private-Mode)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const banner = renderHook(() => useCookieConsent())
    const waiter = renderHook(() => useCookieConsent())
    act(() => banner.result.current.acknowledge())
    expect(waiter.result.current.isDecided).toBe(true)
  })

  it('uebernimmt die Kenntnisnahme aus einem anderen Tab (storage-Event)', () => {
    const { result } = renderHook(() => useCookieConsent())
    act(() => {
      window.localStorage.setItem(CONSENT_STORAGE_KEY, 'acknowledged')
      window.dispatchEvent(new StorageEvent('storage', { key: CONSENT_STORAGE_KEY }))
    })
    expect(result.current.isDecided).toBe(true)
  })

  it('haengt das Event beim Unmount ab', () => {
    const banner = renderHook(() => useCookieConsent())
    const waiter = renderHook(() => useCookieConsent())
    const remove = vi.spyOn(window, 'removeEventListener')
    waiter.unmount()
    expect(remove).toHaveBeenCalledWith('who2be:cookie-consent-acknowledged', expect.any(Function))
    act(() => banner.result.current.acknowledge())
  })
})
