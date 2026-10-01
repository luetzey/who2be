import { act, renderHook } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it } from 'vitest'

import { SHOW_MORE_STEP, useShowMore } from './useShowMore'

const items = Array.from({ length: 20 }, (_, i) => i)

function setup(enabled: boolean, resetKey = '') {
  const listRef = createRef<HTMLElement>()
  return renderHook(
    ({ on, key }) => useShowMore(items, { enabled: on, listRef, resetKey: key }),
    { initialProps: { on: enabled, key: resetKey } },
  )
}

describe('useShowMore', () => {
  it('liefert ohne enabled alle Eintraege und keinen Knopf', () => {
    const { result } = setup(false)
    expect(result.current.visible).toHaveLength(20)
    expect(result.current.nextCount).toBe(0)
    expect(result.current.liveMessage).toBe('')
  })

  it('kuerzt auf die Schrittweite und meldet erst nach dem Klick', () => {
    const { result } = setup(true)
    expect(SHOW_MORE_STEP).toBe(8)
    expect(result.current.visible).toEqual(items.slice(0, 8))
    expect(result.current.buttonLabel).toBe('8 weitere anzeigen')
    expect(result.current.liveMessage).toBe('')

    act(() => result.current.showMore())
    expect(result.current.visible).toHaveLength(16)
    expect(result.current.nextCount).toBe(4)
    expect(result.current.liveMessage).toBe('16 von 20 angezeigt')
  })

  it('setzt bei neuem resetKey auf die erste Schrittweite zurueck', () => {
    const { result, rerender } = setup(true, 'a')
    act(() => result.current.showMore())
    expect(result.current.visible).toHaveLength(16)

    rerender({ on: true, key: 'b' })
    expect(result.current.visible).toHaveLength(8)
    expect(result.current.liveMessage).toBe('')
  })
})
