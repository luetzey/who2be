import { render, screen } from '@testing-library/react'
import { User } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { MetaPill } from './MetaPill'

describe('MetaPill', () => {
  it('rendert Text mit neutralem muted-Default', () => {
    render(<MetaPill>5 Playbooks</MetaPill>)
    const pill = screen.getByText('5 Playbooks')
    expect(pill.className).toContain('bg-muted')
  })

  it('faerbt nur das Icon ueber iconTone (neutrales Muster)', () => {
    const { container } = render(
      <MetaPill icon={User} iconTone="persona">
        Coach Carla
      </MetaPill>,
    )
    const svg = container.querySelector('svg')
    expect(svg?.getAttribute('class')).toContain('text-pill-persona-fg')
    expect(svg?.getAttribute('aria-hidden')).toBe('true')
  })

  it('rendert eine voll tonale Pille ueber tone', () => {
    render(<MetaPill tone="resource">policy</MetaPill>)
    expect(screen.getByText('policy').className).toContain('bg-pill-resource')
  })

  it('rendert die destructive-Variante fuer Warn-Marker', () => {
    render(<MetaPill tone="destructive">Persona fehlt</MetaPill>)
    expect(screen.getByText('Persona fehlt').className).toContain('text-destructive')
  })
})
