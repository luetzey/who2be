import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Checkbox } from './checkbox'
import { RadioGroup, RadioGroupItem } from './radio-group'

// Hit-Target-Vertrag (Primitive-Fund 3 aus dem Audit #570 Haelfte A).
//
// docs/frontend/design-language.md §11 setzt den verbindlichen Floor auf
// >= 32px, "kein interaktives Element darf darunter liegen, auf keinem
// Breakpoint". Checkbox und RadioGroupItem messen 16px — sie unterschreiten
// ihn um die Haelfte.
//
// Die visuelle Box bleibt dabei ausdruecklich 16px (Karte: "Label-Kopplung /
// Padding-Huelle, nicht `size`"). Wachsen soll allein die klickbare Flaeche.
// Beide Primitive loesen das unterschiedlich, weil ihr DOM sich unterscheidet:
//
//  - Checkbox rendert ein `<input>`. Das ist ein replaced element und
//    rendert KEINE Pseudoelemente — `before:h-8` daran blieb gemessen
//    wirkungslos (Hitbox 16,5px). Also traegt der Huell-`span` die Optik und
//    der `input` wird selbst zur transparenten 32x32-Flaeche darueber.
//  - RadioGroupItem rendert einen Radix-`<button>`. Dort greift ein
//    Pseudoelement, die Optik bleibt unangetastet.
//
// jsdom hat kein Layout; das hier ist ein Klassen-Vertrag. Die gerenderten
// Groessen sind in
// .claude/plan/2026-09-23-1700_primitives-tabslist-entitycard-hit-target.md
// belegt (Chromium gegen das gebaute Stylesheet, Hitflaeche per
// elementFromPoint-Raster gemessen, 320 und 768px).

describe('Checkbox — Hit-Target (Primitive-Fund #570/A)', () => {
  it('haelt die sichtbare Box bei 16px', () => {
    const { container } = render(<Checkbox id="cb" />)
    const box = container.querySelector('span')
    expect(box).toHaveClass('h-4', 'w-4')
  })

  // 32px Hitflaeche, ueber der 16px-Box zentriert. `-translate-x-1/2`
  // zusammen mit `top-1/2 left-1/2` zentriert sie, statt sie nach rechts
  // unten zu verschieben — ohne die Translate-Klassen laege die Flaeche
  // ausserhalb der sichtbaren Box.
  it('vergroessert die klickbare Flaeche des Controls auf 32px', () => {
    render(<Checkbox id="cb" />)
    const input = screen.getByRole('checkbox')
    expect(input).toHaveClass('h-8', 'w-8')
    expect(input).toHaveClass('top-1/2', 'left-1/2', '-translate-x-1/2', '-translate-y-1/2')
  })

  // Die Zustands-Optik musste vom `input` an den `span` wandern. Dort greift
  // `peer-*` NICHT: `peer-*` adressiert ein Geschwister, der `span` ist aber
  // der Elternknoten des `input`. Gemessen blieb der Hintergrund mit
  // `peer-checked:` in allen vier Zustaenden weiss; mit `has-[:checked]:`
  // trifft er wieder exakt den Ausgangswert (oklch(0.205 0 0)).
  it('haengt die Zustands-Optik per has-[] an den Huell-span, nicht per peer-[]', () => {
    const { container } = render(<Checkbox id="cb" />)
    const box = container.querySelector('span')
    expect(box).toHaveClass('has-[:checked]:bg-primary', 'has-[:checked]:border-primary')
    expect(box).toHaveClass('has-[:disabled]:opacity-50')
    expect(box).toHaveClass('has-[:focus-visible]:ring-2', 'has-[:focus-visible]:ring-ring')
  })

  // Der Haken bleibt an `peer-checked:` — korrekt, denn das <svg> IST ein
  // Geschwister des Inputs. Regressionssicherung gegen ein pauschales
  // Umschreiben auf has-[].
  it('laesst den Haken am peer-Selektor (das svg ist ein Geschwister)', () => {
    const { container } = render(<Checkbox id="cb" />)
    expect(container.querySelector('svg')).toHaveClass('peer-checked:opacity-100')
  })
})

describe('RadioGroupItem — Hit-Target (Primitive-Fund #570/A)', () => {
  function renderItem() {
    render(
      <RadioGroup aria-label="Preset">
        <RadioGroupItem value="a" id="r-a" />
      </RadioGroup>,
    )
    return screen.getByRole('radio')
  }

  it('haelt die sichtbare Box bei 16px', () => {
    expect(renderItem()).toHaveClass('h-4', 'w-4')
  })

  // Anders als bei der Checkbox darf das Control selbst die Flaeche tragen:
  // der Radix-Item ist ein <button>, kein replaced element.
  it('vergroessert die klickbare Flaeche per Pseudoelement auf 32px', () => {
    const item = renderItem()
    expect(item).toHaveClass('before:h-8', 'before:w-8')
    expect(item).toHaveClass(
      'before:absolute',
      'before:top-1/2',
      'before:left-1/2',
      'before:-translate-x-1/2',
      'before:-translate-y-1/2',
    )
  })

  // `before:absolute` braucht einen positionierten Vorfahren, sonst bezieht
  // sich die Flaeche auf irgendeinen Container weiter oben.
  it('positioniert das Control, damit die Flaeche daran haengt', () => {
    expect(renderItem()).toHaveClass('relative')
  })

  // `content-[""]` ist nicht kosmetisch: ohne content-Property rendert ein
  // Pseudoelement ueberhaupt nicht.
  it('setzt content, sonst rendert das Pseudoelement nicht', () => {
    expect(renderItem().className).toContain('before:content-[""]')
  })
})
