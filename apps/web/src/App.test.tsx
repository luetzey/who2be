import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('App', () => {
  it('zeigt ohne Session die Anmeldeseite', async () => {
    render(<App />)
    // findBy*: Der Session-Bootstrap laeuft asynchron — bis er abgeschlossen
    // ist, zeigt RequireAuth eine Ladeanzeige statt sofort zu redirecten.
    expect(await screen.findByRole('heading', { name: 'Anmeldung' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Who2Be' })).toBeInTheDocument()
  })
})
