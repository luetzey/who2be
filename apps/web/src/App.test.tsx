import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App', () => {
  it('rendert die Ueberschrift', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Who2Be' })).toBeInTheDocument()
  })
})
