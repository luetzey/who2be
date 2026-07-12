import { render } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { EntityAvatar, EntityIcon, initialsFromName } from './EntityIcon'

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

describe('initialsFromName', () => {
  it('leitet bis zu zwei Grossbuchstaben ab', () => {
    expect(initialsFromName('Coach Carla')).toBe('CC')
    expect(initialsFromName('support')).toBe('SU')
    expect(initialsFromName('  Max  Otto  Berger ')).toBe('MB')
    expect(initialsFromName('   ')).toBe('?')
  })
})

describe('EntityAvatar', () => {
  it('rendert die Initialen dekorativ in der Tinten-Kachel', () => {
    const { container } = render(<EntityAvatar initials="CC" tone="persona" />)
    const tile = container.firstElementChild as HTMLElement
    expect(tile.className).toContain('bg-pill-persona')
    expect(tile.textContent).toBe('CC')
    expect(tile.getAttribute('aria-hidden')).toBe('true')
  })
})
