import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ThemeProvider } from '@/app/ThemeProvider'

import { CatalogPage } from './CatalogPage'

function renderCatalog() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <CatalogPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('CatalogPage', () => {
  it('rendert die Hauptueberschrift', () => {
    renderCatalog()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Component-Catalog' }),
    ).toBeInTheDocument()
  })

  it('zeigt alle Primitive-Sektionen', () => {
    renderCatalog()
    for (const title of [
      'Button',
      'Input',
      'Textarea',
      'Label',
      'Checkbox',
      'Card',
      'Badge',
      'Alert',
      'Dialog',
      'Dropdown-Menu',
      'Form',
      'Skeleton',
      'Table',
    ]) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
  })

  it('zeigt Layout- und Data-Sektionen', () => {
    renderCatalog()
    expect(screen.getByRole('heading', { name: 'Layout-Primitives' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Data-Komponenten' })).toBeInTheDocument()
  })
})
