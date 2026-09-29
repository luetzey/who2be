import { act, fireEvent, render, screen } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { FormProvider, useForm } from 'react-hook-form'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PersonaProfileFields } from '@/features/personas/components/PersonaProfileFields'
import type { PersonaEditorValues } from '@/features/personas/hooks/usePersonaForm'
import { axe } from '@/test/a11y'

import { DetailHeader } from './DetailHeader'
import { ExpandableText } from './ExpandableText'

// Einsatzort Persona-Legacy-Hinweis (M8): der pill-faehige Profil-Editor zieht
// BlockNote hoch (ProseMirror mountet nicht in jsdom) — gestubt wie in
// `PersonaProfileFields.test.tsx`.
vi.mock('@/features/personas/components/PersonaProfileEditor', () => ({
  PersonaProfileEditor: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))
vi.mock('@/api/useApi', () => ({
  useApi: () => ({ listPersonaTags: vi.fn().mockResolvedValue([]) }),
}))

// jsdom hat kein Layout: `scrollHeight`/`clientHeight` sind immer 0. Die
// Kuerzung misst genau diese beiden Werte, also werden sie hier gesetzt —
// „ueberlaeuft" heisst: Inhalt 400 px, sichtbar 60 px (3 Zeilen).
let overflowing = false
let observerCallbacks: ResizeObserverCallback[] = []

class ResizeObserverStub {
  constructor(cb: ResizeObserverCallback) {
    observerCallbacks.push(cb)
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

const originalResizeObserver = globalThis.ResizeObserver

beforeEach(() => {
  overflowing = false
  observerCallbacks = []
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver
  vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(() =>
    overflowing ? 400 : 60,
  )
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(() => 60)
})

afterEach(() => {
  vi.restoreAllMocks()
  globalThis.ResizeObserver = originalResizeObserver
})

const LONG =
  'Diese Persona fuehrt Support-Gespraeche nach den Richtlinien unter ' +
  'https://intranet.example.com/richtlinien/support/eskalation-und-rabatte-2026 ' +
  'und eskaliert Rabattanfragen an das Team. '.repeat(10)

function fireResize() {
  act(() => {
    for (const cb of observerCallbacks) cb([], {} as ResizeObserver)
  })
}

describe('ExpandableText', () => {
  it('zeigt bei kurzem Text keinen Knopf', () => {
    render(<ExpandableText text="Kurzer Text." />)
    expect(screen.getByText('Kurzer Text.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('rendert bei leerem Text nichts', () => {
    const { container } = render(<ExpandableText text="" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('kuerzt langen Text auf N Zeilen und bietet „Mehr anzeigen" an', () => {
    overflowing = true
    render(<ExpandableText text={LONG} lines={3} mdLines={6} />)

    const button = screen.getByRole('button', { name: 'Mehr anzeigen' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    // Echter Button, per Tastatur erreichbar.
    expect(button.tagName).toBe('BUTTON')
    expect(button).toHaveAttribute('type', 'button')

    // `aria-controls` zeigt auf das Textelement; der gekuerzte Text bleibt
    // vollstaendig im DOM, der Screenreader liest alles.
    const textEl = document.getElementById(button.getAttribute('aria-controls') ?? '')
    expect(textEl).not.toBeNull()
    expect(textEl).toHaveTextContent(LONG.trim())
    expect(textEl).toHaveClass('line-clamp-(--clamp)', 'md:line-clamp-(--clamp-md)')
    expect(textEl?.style.getPropertyValue('--clamp')).toBe('3')
    expect(textEl?.style.getPropertyValue('--clamp-md')).toBe('6')
    // Umbruch auch in einer URL ohne Trennstelle (M1).
    expect(textEl).toHaveClass('wrap-anywhere')
  })

  it('klappt im Seitenfluss auf, ohne inneren Scrollbereich, und wieder zu', () => {
    overflowing = true
    render(<ExpandableText text={LONG} />)

    const button = screen.getByRole('button', { name: 'Mehr anzeigen' })
    const textEl = document.getElementById(button.getAttribute('aria-controls') ?? '')!

    button.focus()
    fireEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAccessibleName('Weniger anzeigen')
    expect(textEl).not.toHaveClass('line-clamp-(--clamp)')
    // Kein innerer Scroller: weder Hoehenkappe noch overflow-auto/scroll.
    expect(textEl.className).not.toMatch(/max-h-|overflow-(auto|scroll|y-auto)/)
    // Fokus bleibt auf dem Knopf (derselbe Knoten, nur neu beschriftet).
    expect(button).toHaveFocus()

    fireEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveAccessibleName('Mehr anzeigen')
    expect(textEl).toHaveClass('line-clamp-(--clamp)')
  })

  it('ist per Tastatur erreichbar: nativer Button, nicht aus der Tab-Folge genommen', () => {
    overflowing = true
    render(<ExpandableText text={LONG} />)
    const button = screen.getByRole('button', { name: 'Mehr anzeigen' })
    // Ein natives <button type="button"> loest Enter/Leertaste selbst als
    // click aus; entscheidend ist, dass es fokussierbar bleibt.
    expect(button).not.toHaveAttribute('tabindex', '-1')
    expect(button).not.toHaveAttribute('aria-hidden')
    button.focus()
    expect(button).toHaveFocus()
  })

  it('hat mobil eine Trefferflaeche von mindestens 44 px, ab md 32 px', () => {
    overflowing = true
    render(<ExpandableText text={LONG} />)
    const button = screen.getByRole('button', { name: 'Mehr anzeigen' })
    expect(button).toHaveClass('min-h-11', 'md:min-h-8')
  })

  it('misst neu, wenn sich die Groesse aendert (Drehung, Textzoom)', () => {
    render(<ExpandableText text={LONG} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()

    overflowing = true
    fireResize()
    expect(screen.getByRole('button', { name: 'Mehr anzeigen' })).toBeInTheDocument()

    overflowing = false
    fireResize()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('holt beim Zuklappen den Textanfang nur zurueck, wenn er oberhalb liegt', () => {
    overflowing = true
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const top = vi.spyOn(Element.prototype, 'getBoundingClientRect')
    render(<ExpandableText text={LONG} />)
    const button = screen.getByRole('button', { name: 'Mehr anzeigen' })

    // Textanfang sichtbar: kein Sprung.
    top.mockReturnValue({ top: 120 } as DOMRect)
    fireEvent.click(button)
    fireEvent.click(button)
    expect(scrollIntoView).not.toHaveBeenCalled()

    // Textanfang oberhalb des Viewports: zurueckholen.
    top.mockReturnValue({ top: -300 } as DOMRect)
    fireEvent.click(button)
    fireEvent.click(button)
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start' })
  })

  it('rendert das gewuenschte Element', () => {
    render(<ExpandableText as="pre" text="a  b" data-testid="et" />)
    expect(screen.getByTestId('et').querySelector('pre')).toHaveTextContent('a b')
  })

  it('hat gekuerzt und aufgeklappt keine axe-Violations', async () => {
    overflowing = true
    const { container } = render(<ExpandableText text={LONG} />)
    expect(await axe(container)).toHaveNoViolations()
    fireEvent.click(screen.getByRole('button', { name: 'Mehr anzeigen' }))
    expect(await axe(container)).toHaveNoViolations()
  })
})

// Einsatzorte laut Spec M2/M8. Die Layout-Aussagen (Oberkante der Tab-Leiste,
// kein innerer Scroller) sind im Browser gegen das gebaute CSS gemessen
// (Handoff t_bc28b9b1); hier stehen die Vertraege, die jsdom pruefen kann.
describe('ExpandableText im Einsatz', () => {
  it('kuerzt die Beschreibung im Detailkopf: 3 Zeilen mobil, 6 ab md', () => {
    overflowing = true
    render(
      <MemoryRouter>
        <DetailHeader icon={FileText} iconTone="tools" title="Support" description={LONG} />
      </MemoryRouter>,
    )
    const button = screen.getByRole('button', { name: 'Mehr anzeigen' })
    const textEl = document.getElementById(button.getAttribute('aria-controls') ?? '')!
    expect(textEl).toHaveTextContent(LONG.trim())
    expect(textEl).toHaveClass('line-clamp-(--clamp)', 'text-sm', 'text-muted-foreground')
    expect(textEl.style.getPropertyValue('--clamp')).toBe('3')
    expect(textEl.style.getPropertyValue('--clamp-md')).toBe('6')
  })

  it('zeigt im Detailkopf bei kurzer Beschreibung keinen Knopf', () => {
    render(
      <MemoryRouter>
        <DetailHeader icon={FileText} iconTone="tools" title="Support" description="Kurz." />
      </MemoryRouter>,
    )
    expect(screen.getByText('Kurz.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mehr anzeigen' })).not.toBeInTheDocument()
  })

  function PersonaHarness({ legacySystemPrompt }: { legacySystemPrompt: string }) {
    const form = useForm<PersonaEditorValues>({
      defaultValues: {
        name: 'Coach',
        description: 'Desc',
        profileBlocks: [],
        tags: [],
        modes: [],
        skills: [],
      },
    })
    return (
      <MemoryRouter>
        <FormProvider {...form}>
          <PersonaProfileFields
            form={form}
            formKey="p1-1"
            initialProfileBlocks={[]}
            legacySystemPrompt={legacySystemPrompt}
          />
        </FormProvider>
      </MemoryRouter>
    )
  }

  it('zeigt den Persona-Legacy-Hinweis ohne inneren Scrollbereich (M8)', () => {
    overflowing = true
    render(<PersonaHarness legacySystemPrompt={LONG} />)
    const hint = screen.getByTestId('persona-legacy-system-prompt-hint')
    const pre = hint.querySelector('pre')!
    expect(pre).toHaveTextContent(LONG.trim())
    // Vorher `max-h-40 overflow-auto`: 160 px sichtbar von 3.312 px.
    expect(pre.className).not.toMatch(/max-h-|overflow-(auto|scroll|y-auto)/)
    expect(pre).toHaveClass('line-clamp-(--clamp)', 'font-mono', 'whitespace-pre-wrap')
    expect(pre.style.getPropertyValue('--clamp')).toBe('6')
    expect(hint).toContainElement(screen.getByRole('button', { name: 'Mehr anzeigen' }))
  })
})
