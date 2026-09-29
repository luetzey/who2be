import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import i18n from '@/i18n'
import { axe } from '@/test/a11y'

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: {
    apiBaseUrl: 'http://localhost:8000',
    mcpUrl: 'http://localhost:8000/mcp',
    supabaseUrl: 'http://localhost:54321',
    supabaseAnonKey: 'anon',
    signupDisabled: false,
    launchMode: 'open' as 'open' | 'coming_soon',
    launchContact: '',
    turnstileSiteKey: '',
  },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

vi.mock('@/lib/supabase', () => ({
  syncStorageBackendForThisTab: vi.fn(),
  supabase: {
    auth: {
      signUp: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInWithPassword: vi.fn(),
      resend: vi.fn(),
      signOut: vi.fn(),
      mfa: { getAuthenticatorAssuranceLevel: vi.fn(), listFactors: vi.fn() },
    },
  },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/session-context', () => ({
  useSession: () => ({ session: null, me: null }),
}))

import { LoginPage } from '@/features/auth/pages/LoginPage'
import { SignupPage } from '@/features/auth/pages/SignupPage'

import { Wordmark } from './Wordmark'

const TAGLINE = {
  en: 'Agent configuration you review — not agent behavior you hope for.',
  de: 'Agent-Konfiguration, die du prüfst — nicht Agent-Verhalten, auf das du hoffst.',
}

const PAGES = [
  ['LoginPage', '/login', LoginPage],
  ['SignupPage', '/signup', SignupPage],
] as const

function renderAt(path: string, Page: () => React.JSX.Element | null) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Page />
    </MemoryRouter>,
  )
}

describe('Auth-Karte: Wortmarke A und Einzeiler (Audit A5, E6-A)', () => {
  for (const [name, path, Page] of PAGES) {
    for (const lang of ['de', 'en'] as const) {
      it(`${name} (${lang}): Wortmarke als benanntes Bild, Einzeiler sichtbar, keine Versal-Eyebrow`, async () => {
        await i18n.changeLanguage(lang)
        const { container } = renderAt(path, Page)

        const mark = screen.getByRole('img', { name: 'Who2Be' })
        expect(mark).toBe(screen.getByTestId('wordmark'))
        // Wortmarke sitzt in der Karte ueber dem Titel, nicht irgendwo.
        const heading = screen.getByRole('heading', { level: 2 })
        expect(mark.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

        expect(screen.getByText(TAGLINE[lang])).toBeVisible()

        // Die fruehere 12-px-Versalzeile "WHO2BE" ist weg.
        expect(container.querySelector('span.uppercase')).toBeNull()
        expect(screen.queryByText('Who2Be', { selector: 'span' })).toBeNull()
      })
    }

    it(`${name}: keine axe-Verstoesse mit Wortmarke`, async () => {
      await i18n.changeLanguage('de')
      const { container } = renderAt(path, Page)
      expect(await axe(container)).toHaveNoViolations()
    })
  }
})

describe('Wordmark: deckungsgleich mit dem Brand-Asset', () => {
  const asset = readFileSync(
    resolve(__dirname, '../../../../../docs/assets/brand/logo-light.svg'),
    'utf8',
  )
  // Nur die Glyphen-Gruppe (zweites <g>), nicht der Halo fuer GitHub.
  const glyphs = asset.split('<g>')[1]
  const assetPaths = [...glyphs.matchAll(/<path fill="(#[0-9a-f]+)" transform="([^"]+)" d="([^"]+)"/g)]

  it('uebernimmt alle sechs Glyphen-Pfade unveraendert aus logo-light.svg', () => {
    const { container } = render(<Wordmark label="Who2Be" />)
    const paths = [...container.querySelectorAll('path')]
    expect(assetPaths).toHaveLength(6)
    expect(paths.map((p) => [p.getAttribute('transform'), p.getAttribute('d')])).toEqual(
      assetPaths.map((m) => [m[2], m[3]]),
    )
  })

  it('faerbt genau die "2" in der Akzentfarbe, den Rest in --foreground (Theme folgt ohne JS)', () => {
    const { container } = render(<Wordmark label="Who2Be" />)
    const paths = [...container.querySelectorAll('path')]
    const expected = assetPaths.map((m) =>
      m[1] === '#0a0a0a' ? 'fill-foreground' : 'fill-wordmark-accent',
    )
    expect(paths.map((p) => p.getAttribute('class'))).toEqual(expected)
    expect(expected.filter((c) => c === 'fill-wordmark-accent')).toHaveLength(1)
  })
})
