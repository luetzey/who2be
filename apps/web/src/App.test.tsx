import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App', () => {
  it('zeigt ohne Session die Anmeldeseite', () => {
    render(<App />)
    expect(
      screen.getByRole('heading', { name: 'Who2Be — Anmeldung' }),
    ).toBeInTheDocument()
  })
})
