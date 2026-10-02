import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { COUNT_PILL_TEXT, CountPill } from './CountPill'

// Audit A12: Kontrast der Zaehler-Pill. Die Messung selbst steht in
// `styles/brand-contrast.test.ts`; hier der Klassen- und Einbau-Vertrag.

const PAGES = [
  'features/agents/pages/AgentsPage.tsx',
  'features/playbooks/pages/PlaybooksPage.tsx',
  'features/system-prompts/pages/SystemPromptsPage.tsx',
  'features/tools/pages/ToolsPage.tsx',
]

describe('CountPill', () => {
  it('zeigt die Zahl mit text-foreground/70 statt text-muted-foreground', () => {
    render(<CountPill count={12} label="12 Agents" />)
    const pill = screen.getByTestId('count-pill')
    expect(pill).toHaveTextContent('12')
    expect(pill).toHaveAttribute('aria-label', '12 Agents')
    expect(COUNT_PILL_TEXT).toBe('text-foreground/70')
    expect(pill.className).toContain('text-foreground/70')
    expect(pill.className).toContain('bg-muted')
    expect(pill.className).not.toContain('text-muted-foreground')
  })

  it('ohne label setzt sie kein leeres aria-label', () => {
    render(<CountPill count={3} />)
    expect(screen.getByTestId('count-pill')).not.toHaveAttribute('aria-label')
  })

  for (const page of PAGES) {
    it(`${page} nutzt CountPill und keine eigene Pill mehr`, () => {
      const source = readFileSync(resolve(__dirname, '../..', page), 'utf8')
      expect(source).toContain('<CountPill')
      expect(source).not.toMatch(/rounded-full bg-muted px-2 py-0\.5 text-sm font-medium text-muted-foreground/)
    })
  }
})
