import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'

import { PlaybookComposesPicker } from './PlaybookComposesPicker'

// Responsive-Vertrag #573 (Haelfte A). Die Zahl 40 px stammt aus AK 5 dieses
// Issues, NICHT aus der Norm: `docs/frontend/design-language.md` §11 ist die
// einzige Quelle des Hit-Target-Floors und setzt ihn auf >= 32 px. Die hier
// gemessenen 24 px der Zeilen-Aktionen unterschreiten diesen Norm-Floor und
// waeren auch ohne das AK ein Defekt.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1700_573-w3-playbooks-haelfte-a-responsive.md
// gegen das gebaute Stylesheet in Chromium belegt.

const listPlaybooksMock = vi.fn()
const stableApi = { listPlaybooks: listPlaybooksMock }

vi.mock('@/api/useApi', () => ({
  useApi: () => stableApi,
}))

const makePlaybook = (id: string, name: string): Playbook => ({
  id,
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name,
  current_version: 1,
  type: 'workflow',
  tags: [],
  triggers: null,
  content: {
    description: `Beschreibung von ${name}`,
    body: '',
    type: 'workflow',
    tags: [],
    triggers: null,
  },
  created_at: 't',
  updated_at: 't',
})

// Bewusst pessimistische Fixture: ein langer, trennstellenarmer Kind-Name ist
// in dieser Domaene der Regelfall, nicht der Ausreisser.
const child = makePlaybook('pb-a', 'Gespraechsleitfaden-Erstkontakt-Enterprise')

async function openPicker(): Promise<HTMLElement> {
  listPlaybooksMock.mockResolvedValue([child])
  render(
    <PlaybookComposesPicker
      currentPlaybookId="pb-current"
      existing={[child]}
      saving={false}
      onSave={vi.fn()}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Sub-Playbooks bearbeiten' }))
  const list = await screen.findByRole('list', { name: 'Ausgewaehlte Sub-Playbooks' })
  return list
}

describe('PlaybookComposesPicker — Responsive (#573)', () => {
  it('laesst die Kind-Zeile umbrechen statt ueberlaufen', async () => {
    const list = await openPicker()

    // Gemessen: die Zeile braucht mindestens 319,1 px, der Dialog-Innenraum
    // misst bei 320 px Viewport 238 px. Weil `DialogContent` ein `grid` ist,
    // zieht die Zeile den ganzen Dialog auf. Vorentscheidung 1 des Issues:
    // umbrechen, kein Overflow-Menue.
    const [row] = await waitFor(() => {
      const rows = list.querySelectorAll('li')
      expect(rows.length).toBeGreaterThan(0)
      return [...rows]
    })
    expect(row).toHaveClass('flex-wrap')

    // Der Name muss zusaetzlich schrumpfen duerfen, sonst haelt er die Zeile
    // ueber ihre min-content-Breite auf.
    const name = row.querySelector('span')
    expect(name).toHaveClass('min-w-0')
  })

  it('haelt die drei Zeilen-Aktionen auf dem 40-px-Hit-Target aus AK 5', async () => {
    await openPicker()

    // Gemessen 24 x 24 px (`h-6 w-6`) bzw. 24 px hoch (`h-6`) — unter dem
    // Norm-Floor aus §11 (>= 32 px) und unter AK 5 (40 px).
    const up = await screen.findByRole('button', {
      name: `${child.name} nach oben verschieben`,
    })
    const down = screen.getByRole('button', {
      name: `${child.name} nach unten verschieben`,
    })
    for (const btn of [up, down]) {
      expect(btn).toHaveClass('h-10')
      expect(btn).toHaveClass('w-10')
      expect(btn).toHaveClass('md:h-6')
      expect(btn).toHaveClass('md:w-6')
    }

    const remove = screen.getAllByRole('button', { name: 'Entfernen' })[0]
    expect(remove).toHaveClass('h-10')
    expect(remove).toHaveClass('md:h-6')
  })
})
