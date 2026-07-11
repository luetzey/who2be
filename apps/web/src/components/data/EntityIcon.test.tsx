import { render } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { EntityIcon } from './EntityIcon'

describe('EntityIcon', () => {
  it('rendert das Icon dekorativ (aria-hidden) in der Tinten-Kachel', () => {
    const { container } = render(<EntityIcon icon={FileText} tone="resource" />)
    const tile = container.firstElementChild as HTMLElement
    expect(tile.className).toContain('bg-pill-resource')
    expect(tile.className).toContain('text-pill-resource-fg')
    const svg = tile.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg?.getAttribute('aria-hidden')).toBe('true')
  })

  it('mappt die Groesse auf die Kachel- und Icon-Klassen', () => {
    const { container } = render(<EntityIcon icon={FileText} tone="tools" size="lg" />)
    const tile = container.firstElementChild as HTMLElement
    expect(tile.className).toContain('size-12')
    expect(tile.querySelector('svg')?.getAttribute('class')).toContain('size-6')
  })
})
