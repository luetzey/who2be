import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Token } from '@/api/types'

import { AgentTokensSection } from './AgentTokensSection'

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

const mocks = vi.hoisted(() => {
  const listTokens = vi.fn()
  return {
    listTokens,
    api: {
      listTokens,
      createToken: vi.fn(),
      renameToken: vi.fn(),
      rotateToken: vi.fn(),
      revokeToken: vi.fn(),
    },
  }
})

vi.mock('@/api/useApi', () => ({ useApi: () => mocks.api }))

function makeToken(overrides: Partial<Token> = {}): Token {
  return {
    id: 't-1',
    workspace_id: 'ws-1',
    // Token-Praefixe sind strukturell trennstellenfrei — genau der Inhalt, den
    // AK 2 des Issues als Ueberlauf-Kandidaten benennt.
    name: 'w2b_ci_deploy_kundenservice_eskalation_stufe_zwei',
    agent_id: 'a-1',
    created_at: '2026-09-22T14:31:07.482913Z',
    last_used_at: '2026-09-23T08:02:55.119004Z',
    revoked_at: null,
    ...overrides,
  }
}

// Responsive-Vertrag #570 (Haelfte A).
//
// Zur Zahl 40 px: sie kommt aus **AK 4 dieses Issues**, nicht aus der Norm.
// `docs/frontend/design-language.md` §11 ist die einzige Quelle des
// Hit-Target-Floors und setzt ihn auf >= 32 px; 40 px ist dort die Praeferenz
// `size="default"`, und `size="sm"` (36 px) ist ausdruecklich zulaessig. Die
// gemessenen 36 px dieser Datei sind nach der Norm also konform — dieses Paket
// hebt sie unterhalb `md` an, weil sein Akzeptanzkriterium es verlangt.
//
// Die Klassenfolge `min-h-10 md:min-h-0` ist woertlich die aus PR #604
// (`SettingsNav`) und #605 (`WorkAreaNav`, `AreaGrants`) — eine zweite Variante
// desselben Musters waere Pattern Drift.
//
// jsdom hat kein Layout, deshalb sind das hier Klassen-Vertraege. Die
// Layout-Aussagen selbst sind in
// .claude/plan/2026-09-23-1420_570-w3-agents-haelfte-a-responsive-audit.md
// gegen das gebaute CSS in Chromium bei 320 px gerendert belegt.
describe('AgentTokensSection — Responsive (#570)', () => {
  it('laesst den Token-Namen umbrechen statt aus der Zeile zu laufen', async () => {
    mocks.listTokens.mockResolvedValue([makeToken()])
    render(<AgentTokensSection agentId="a-1" />)

    const name = await screen.findByText(
      'w2b_ci_deploy_kundenservice_eskalation_stufe_zwei',
    )
    // Gemessen bei 320 px: der Token-Name zog den umgebenden `Stack` auf
    // 335,5 px in einer 254 px breiten Zeile (+81 px Ueberlauf, Inhalt
    // zusaetzlich abgeschnitten). `break-all`, weil ein `w2b_`-Praefix
    // strukturell keine Trennstelle hat.
    expect(name).toHaveClass('break-all')
  })

  it('gibt der Text-Spalte der Token-Zeile min-w-0 und laesst die Zeitstempel umbrechen', async () => {
    mocks.listTokens.mockResolvedValue([makeToken()])
    render(<AgentTokensSection agentId="a-1" />)

    const name = await screen.findByText(
      'w2b_ci_deploy_kundenservice_eskalation_stufe_zwei',
    )
    // Der `Stack` ist das Text tragende Flex-Kind der `flex-wrap`-Zeile. Ohne
    // `min-w-0` kann es nicht unter seine Inhaltsbreite schrumpfen — das Muster
    // stammt aus `AgentHierarchyView.tsx:59`/`:98` (Vorentscheidung 1).
    expect(name.parentElement).toHaveClass('min-w-0')
    // Die Zeitstempel-Zeile war in der Nachmessung ebenfalls abgeschnitten
    // (ISO-8601 mit Mikrosekunden, zwei Daten in einer Zeile). `break-words`,
    // weil die Zeile aus Saetzen mit Trennstellen besteht.
    expect(screen.getByText(/^erstellt 2026-09-22/)).toHaveClass('break-words')
  })

  it('haelt das 40-px-Hit-Target aus AK 4 an den Zeilen-Aktionen und gibt es ab md frei', async () => {
    mocks.listTokens.mockResolvedValue([makeToken()])
    render(<AgentTokensSection agentId="a-1" />)

    for (const name of ['Umbenennen', 'Rotieren', 'Widerrufen']) {
      const button = await screen.findByRole('button', { name })
      // Gemessen 36 px (`size="sm"`) -> 40 px unterhalb `md`; ab `md` bleibt
      // die Zeilen-Dichte des Desktops erhalten.
      expect(button).toHaveClass('min-h-10')
      expect(button).toHaveClass('md:min-h-0')
    }
  })

  it('laesst das Label der Inaktiv-Disclosure umbrechen und haelt das AK-4-Hit-Target', async () => {
    mocks.listTokens.mockResolvedValue([
      makeToken({ id: 't-exp', expires_at: '2000-01-01T00:00:00Z' }),
      makeToken({ id: 't-old', revoked_at: '2026-02-01T00:00:00Z' }),
    ])
    render(<AgentTokensSection agentId="a-1" />)

    const toggle = await screen.findByRole('button', {
      name: '1 abgelaufene · 1 widerrufene Tokens',
    })
    // Gemessen bei 320 px: 282 px breit in einer 238 px breiten Spalte
    // (+44 px) — das kombinierte Label trifft auf das `whitespace-nowrap` des
    // Button-Primitives. Das war der Verursacher des Body-Scrolls. Mit
    // umbrechendem Text muss die feste `h-9` zu `h-auto` werden, sonst
    // schneidet sie die zweite Zeile ab.
    expect(toggle).toHaveClass('whitespace-normal')
    expect(toggle).toHaveClass('h-auto')
    expect(toggle).toHaveClass('min-h-10')
    expect(toggle).toHaveClass('md:h-9')
    expect(toggle).toHaveClass('md:min-h-0')
  })

  it('laesst die Zaehlerzeile unveraendert — gemessen kein Defekt', async () => {
    mocks.listTokens.mockResolvedValue([makeToken()])
    render(<AgentTokensSection agentId="a-1" />)

    const label = await screen.findByText('Aktive Tokens')
    // Das Issue vermutet hier einen Defekt („`justify-between` ohne
    // `flex-wrap`"). Gemessen passt die Zeile mit grosser Reserve: Label
    // 86,1 px + Zaehler 7,8 px in 238 px (DE), 83,3 px + 31,2 px bei
    // vierstelligem Zaehler (EN). Beide Seiten sind kurze feste Texte —
    // `flex-wrap` haette nichts zu tun. Dieser Test haelt den Nicht-Fund fest,
    // damit die Zeile nicht ohne Messung „mitgefixt" wird.
    expect(label.parentElement).toHaveClass('justify-between')
    expect(label.parentElement).not.toHaveClass('flex-wrap')
  })
})
