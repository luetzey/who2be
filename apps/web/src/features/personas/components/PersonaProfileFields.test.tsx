import { render, screen } from '@testing-library/react'
import { FormProvider, useForm } from 'react-hook-form'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { PersonaProfileFields } from './PersonaProfileFields'
import type { PersonaEditorValues } from '../hooks/usePersonaForm'

// Der pill-faehige Profil-Editor zieht das volle BlockNote-Custom-Schema hoch
// (ProseMirror mountet nicht in jsdom) — gestubt wie im Page-Test.
vi.mock('./PersonaProfileEditor', () => ({
  PersonaProfileEditor: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))
vi.mock('@/api/useApi', () => ({
  useApi: () => ({ listPersonaTags: vi.fn().mockResolvedValue([]) }),
}))

function mode(name: string) {
  return {
    name,
    trigger: '',
    is_default: true,
    identity_add: [],
    output_style_override: [],
    anti_patterns: [],
    playbook_id: null,
    playbook_name: undefined,
  }
}

function Harness({
  modes = [],
  legacySystemPrompt,
}: {
  modes?: PersonaEditorValues['modes']
  legacySystemPrompt?: string
}) {
  const form = useForm<PersonaEditorValues>({
    defaultValues: {
      name: 'Coach',
      description: 'Desc',
      profileBlocks: [],
      tags: [],
      modes,
      skills: [],
    },
  })
  return (
    <MemoryRouter>
      <FormProvider {...form}>
        <PersonaProfileFields
          form={form}
          formKey="p1-1"
          initialProfileBlocks={[]}
          legacySystemPrompt={legacySystemPrompt}
        />
      </FormProvider>
    </MemoryRouter>
  )
}

// Responsive-Vertrag #571 (Haelfte A). Die 40 px stammen aus **AK 3 dieses
// Issues**, nicht aus der Norm: `docs/frontend/design-language.md` §11 ist die
// einzige Quelle des Floors und setzt ihn auf >= 32 px; `size="sm"` (36 px)
// bleibt dort ausdruecklich zulaessig. Dieses Paket hebt den Wert unterhalb
// `md` an, weil sein Akzeptanzkriterium es verlangt.
//
// jsdom hat kein Layout, deshalb Klassen-Vertraege; die Layout-Aussagen sind in
// `.claude/plan/2026-09-23-1500_571a-w3-personas-responsive-audit.md` gerendert
// belegt (Chromium gegen das gebaute CSS, 320/375/768/1024 px).
describe('PersonaProfileFields — Responsive (#571)', () => {
  it('laesst den Modi-Info-Pill umbrechen und haelt das Hit-Target aus AK 3', () => {
    render(<Harness modes={[mode('Eskalationsmodus Zahlungsverzug')]} />)

    // Gemessen bei 320 px: die Pille misst 355 px in 238 px verfuegbarer
    // Breite und lief 118 px ueber — ein Modusname ist frei waehlbar und hat
    // keine Laengengrenze. `h-auto` hatte sie ausserdem auf 32 px gedrueckt.
    const pill = screen.getByTestId('persona-modes-info-pill')
    expect(pill).toHaveClass('min-h-10')
    expect(pill).toHaveClass('md:min-h-0')
    expect(pill).toHaveClass('max-w-full')
    expect(pill).toHaveClass('flex-wrap')
    expect(pill).toHaveClass('whitespace-normal')
    expect(pill).toHaveClass('break-words')
    // tailwind-merge muss das `whitespace-nowrap` der Button-Basis entfernt
    // haben — sonst bleibt die Pille trotz `flex-wrap` einzeilig.
    expect(pill).not.toHaveClass('whitespace-nowrap')
  })

  it('bricht den Legacy-System-Prompt an Bezeichnern ohne Trennstelle um', () => {
    render(
      <Harness
        modes={[mode('Standard')]}
        legacySystemPrompt="keine_rabattzusage_ohne_freigabe_durch_den_teamleiter_vertrieb"
      />,
    )

    // Gemessen bei 320 px: 462 px Inhalt in 212 px sichtbarer Breite —
    // `whitespace-pre-wrap` allein bricht nur an Leerzeichen.
    const hint = screen.getByTestId('persona-legacy-system-prompt-hint')
    const pre = hint.querySelector('pre')
    expect(pre).not.toBeNull()
    expect(pre).toHaveClass('break-words')
    expect(pre).toHaveClass('whitespace-pre-wrap')
  })
})
