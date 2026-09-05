import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: { launchContact: '' },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import { ComingSoonPage } from './ComingSoonPage'

afterEach(() => {
  mockConfig.launchContact = ''
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/signup']}>
      <ComingSoonPage />
    </MemoryRouter>,
  )
}

describe('ComingSoonPage (a11y)', () => {
  it('hat keine axe-Violations ohne Kontakt-Block', async () => {
    const { container } = renderPage()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)

    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit gesetztem Kontakt-Block', async () => {
    mockConfig.launchContact = 'hello@who2be.dev'
    const { container } = renderPage()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)

    expect(await axe(container)).toHaveNoViolations()
  })
})
