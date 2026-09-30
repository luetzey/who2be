import { fireEvent, render, screen } from '@testing-library/react'
import { createRef, useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fitToContent, supportsFieldSizing } from '@/hooks/useAutoGrow'

import { Textarea } from './textarea'

// Mobil-Spec M5: Textfelder wachsen mit dem Inhalt bis 60 svh, statt innen zu
// scrollen. Zwei Pfade:
// - Browser mit `field-sizing: content` (Chromium, Safari >= 26.2, Firefox
//   >= 152): reines CSS, kein JavaScript setzt eine Hoehe.
// - Browser ohne: `useAutoGrow` setzt `height = scrollHeight` beim Tippen.
// JSDOM rechnet kein Layout; `scrollHeight` wird deshalb je Element gesetzt.

function stubFieldSizing(supported: boolean) {
  const supports = vi.fn((property: string, value?: string) =>
    property === 'field-sizing' && value === 'content' ? supported : false,
  )
  vi.stubGlobal('CSS', { supports })
  return supports
}

function setScrollHeight(el: HTMLElement, px: number) {
  Object.defineProperty(el, 'scrollHeight', { configurable: true, get: () => px })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Textarea — Klassenvertrag (M5)', () => {
  it('waechst standardmaessig mit dem Inhalt und hat die 60-svh-Obergrenze', () => {
    stubFieldSizing(true)
    render(<Textarea aria-label="Notiz" />)
    const field = screen.getByLabelText('Notiz')
    expect(field).toHaveClass('field-sizing-content')
    expect(field).toHaveClass('max-h-[60svh]')
    // Die bisherige Mindesthoehe bleibt.
    expect(field).toHaveClass('min-h-20')
  })

  it('haelt rows als Mindesthoehe, weil field-sizing rows sonst ignoriert', () => {
    stubFieldSizing(true)
    render(<Textarea aria-label="Notiz" rows={4} />)
    const field = screen.getByLabelText('Notiz')
    expect(field).toHaveAttribute('rows', '4')
    expect(field.style.minHeight).toContain('4lh')
    expect(field.style.minHeight).toContain('5rem')
  })

  it('autoGrow={false} laesst Hoehe und rows wie bisher (Token, Konfiguration)', () => {
    stubFieldSizing(false)
    render(<Textarea aria-label="Token" autoGrow={false} rows={2} value="abc" readOnly />)
    const field = screen.getByLabelText('Token')
    expect(field).not.toHaveClass('field-sizing-content')
    expect(field).not.toHaveClass('max-h-[60svh]')
    expect(field.style.minHeight).toBe('')
    expect(field.style.height).toBe('')
  })

  it('reicht Objekt- und Funktions-Refs an das Feld durch', () => {
    stubFieldSizing(true)
    const objectRef = createRef<HTMLTextAreaElement>()
    const fnRef = vi.fn()
    const { rerender } = render(<Textarea aria-label="Notiz" ref={objectRef} />)
    expect(objectRef.current).toBe(screen.getByLabelText('Notiz'))
    rerender(<Textarea aria-label="Notiz" ref={fnRef} />)
    expect(fnRef).toHaveBeenCalledWith(screen.getByLabelText('Notiz'))
  })
})

describe('Textarea — Pfad mit field-sizing (CSS)', () => {
  it('setzt keine Hoehe per JavaScript', () => {
    const supports = stubFieldSizing(true)
    render(<Textarea aria-label="Notiz" rows={3} />)
    const field = screen.getByLabelText('Notiz')
    setScrollHeight(field, 640)
    fireEvent.input(field, { target: { value: 'lang\n'.repeat(30) } })
    expect(supports).toHaveBeenCalledWith('field-sizing', 'content')
    expect(field.style.height).toBe('')
  })
})

describe('Textarea — Fallback ohne field-sizing (useAutoGrow)', () => {
  it('waechst beim Tippen auf die Inhaltshoehe', () => {
    stubFieldSizing(false)
    render(<Textarea aria-label="Notiz" rows={3} />)
    const field = screen.getByLabelText('Notiz')
    setScrollHeight(field, 412)
    fireEvent.input(field, { target: { value: 'lang\n'.repeat(20) } })
    expect(field.style.height).toBe('412px')
  })

  it('zaehlt den Rahmen mit (border-box)', () => {
    stubFieldSizing(false)
    render(<Textarea aria-label="Notiz" style={{ borderTopWidth: '1px', borderBottomWidth: '1px' }} />)
    const field = screen.getByLabelText('Notiz')
    field.style.borderStyle = 'solid'
    setScrollHeight(field, 200)
    fireEvent.input(field)
    expect(field.style.height).toBe('202px')
  })

  it('passt die Hoehe an, wenn ein kontrollierter Wert ohne Tippen wechselt', () => {
    stubFieldSizing(false)
    function Controlled() {
      const [value, setValue] = useState('kurz')
      return (
        <>
          <Textarea aria-label="Notiz" value={value} onChange={(e) => setValue(e.target.value)} />
          <button type="button" onClick={() => setValue('lang\n'.repeat(40))}>
            laden
          </button>
        </>
      )
    }
    render(<Controlled />)
    const field = screen.getByLabelText('Notiz')
    setScrollHeight(field, 880)
    fireEvent.click(screen.getByRole('button', { name: 'laden' }))
    expect(field.style.height).toBe('880px')
  })

  it('misst bei Breitenaenderung neu (Drehung, Textzoom), nicht bei reiner Hoehenaenderung', () => {
    stubFieldSizing(false)
    let callback: ResizeObserverCallback = () => undefined
    const observe = vi.fn()
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(cb: ResizeObserverCallback) {
          callback = cb
        }
        observe = observe
        disconnect = vi.fn()
        unobserve = vi.fn()
      },
    )
    render(<Textarea aria-label="Notiz" />)
    const field = screen.getByLabelText('Notiz')
    expect(observe).toHaveBeenCalledWith(field)

    setScrollHeight(field, 300)
    callback([], {} as ResizeObserver)
    expect(field.style.height).not.toBe('300px')

    Object.defineProperty(field, 'clientWidth', { configurable: true, get: () => 180 })
    callback([], {} as ResizeObserver)
    expect(field.style.height).toBe('300px')
  })

  it('ist mit autoGrow={false} aus', () => {
    stubFieldSizing(false)
    render(<Textarea aria-label="Token" autoGrow={false} />)
    const field = screen.getByLabelText('Token')
    setScrollHeight(field, 500)
    fireEvent.input(field)
    expect(field.style.height).toBe('')
  })

  it('gibt die Hoehe beim Abbau wieder frei', () => {
    stubFieldSizing(false)
    const { rerender } = render(<Textarea aria-label="Notiz" />)
    const field = screen.getByLabelText('Notiz')
    setScrollHeight(field, 260)
    fireEvent.input(field)
    expect(field.style.height).toBe('260px')
    rerender(<Textarea aria-label="Notiz" autoGrow={false} />)
    expect(field.style.height).toBe('')
  })

  it('Fokus und Scrollposition springen beim Wachsen nicht', () => {
    stubFieldSizing(false)
    render(
      <div data-testid="scroller" style={{ overflow: 'auto' }}>
        <Textarea aria-label="Notiz" />
      </div>,
    )
    const scroller = screen.getByTestId('scroller')
    const field = screen.getByLabelText('Notiz')
    let top = 120
    Object.defineProperty(scroller, 'scrollTop', {
      configurable: true,
      get: () => top,
      set: (v: number) => {
        top = v
      },
    })
    // Das kurze `height: auto` verkuerzt den Inhalt, der Browser zieht die
    // Scrollposition nach oben — hier nachgestellt beim Lesen von scrollHeight.
    Object.defineProperty(field, 'scrollHeight', {
      configurable: true,
      get: () => {
        top = 0
        return 480
      },
    })
    field.focus()
    fireEvent.input(field, { target: { value: 'lang\n'.repeat(20) } })

    expect(field.style.height).toBe('480px')
    expect(top).toBe(120)
    expect(document.activeElement).toBe(field)
  })
})

describe('supportsFieldSizing / fitToContent', () => {
  it('meldet false ohne CSS-Objekt (alte Umgebungen, SSR)', () => {
    vi.stubGlobal('CSS', undefined)
    expect(supportsFieldSizing()).toBe(false)
  })

  it('fitToContent laesst die Fensterposition unveraendert', () => {
    const el = document.createElement('textarea')
    document.body.appendChild(el)
    setScrollHeight(el, 150)
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    fitToContent(el)
    expect(el.style.height).toBe('150px')
    // JSDOM scrollt nie; ohne Positionsaenderung wird auch nicht zurueckgesetzt.
    expect(scrollTo).not.toHaveBeenCalled()
    scrollTo.mockRestore()
    el.remove()
  })

  it('fitToContent holt eine verschobene Fensterposition zurueck', () => {
    const el = document.createElement('textarea')
    document.body.appendChild(el)
    let y = 300
    const original = Object.getOwnPropertyDescriptor(window, 'scrollY')
    Object.defineProperty(window, 'scrollY', { configurable: true, get: () => y })
    Object.defineProperty(el, 'scrollHeight', {
      configurable: true,
      get: () => {
        y = 40 // Dokument kurz verkuerzt -> Browser klemmt die Position
        return 150
      },
    })
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    fitToContent(el)
    expect(scrollTo).toHaveBeenCalledWith(window.scrollX, 300)
    scrollTo.mockRestore()
    if (original) Object.defineProperty(window, 'scrollY', original)
    el.remove()
  })
})
