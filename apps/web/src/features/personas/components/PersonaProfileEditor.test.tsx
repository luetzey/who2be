import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PersonaProfileEditor } from './PersonaProfileEditor'

// BlockNote/ProseMirror mountet nicht in jsdom — die Insel selbst wird gestubt,
// der umgebende `bn-container` bleibt echt (er traegt den Layout-Vertrag).
// `@blocknote/react` wird partiell gemockt: `createReactInlineContentSpec` baut
// beim Import das Placeholder-Schema (PlaceholderBlock.tsx) und muss echt
// bleiben, sonst wirft der Modul-Import.
vi.mock('@blocknote/react', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@blocknote/react')>()),
  useCreateBlockNote: () => ({ document: [] }),
  SuggestionMenuController: () => null,
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="blocknote-view">{children}</div>
  ),
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))
vi.mock('@/components/editor/system-prompt/PlaceholderPreviewPopover', () => ({
  PlaceholderPreviewPopover: () => null,
}))
vi.mock('@/components/editor/system-prompt/pickers/PlaybookPicker', () => ({
  PlaybookPicker: () => null,
}))
vi.mock('@/components/editor/system-prompt/pickers/ResourcePicker', () => ({
  ResourcePicker: () => null,
}))
vi.mock('@/components/editor/system-prompt/pickers/CatalogScopePicker', () => ({
  CatalogScopePicker: () => null,
}))
vi.mock('@/components/editor/system-prompt/pickers/ResourcesCatalogScopePicker', () => ({
  ResourcesCatalogScopePicker: () => null,
}))
vi.mock('@/components/editor/system-prompt/pickers/ToolPicker', () => ({
  ToolPicker: () => null,
}))

// Responsive-Vertrag #571 (Haelfte A). jsdom hat kein Layout, deshalb ein
// Klassen-Vertrag; die Layout-Aussage ist in
// `.claude/plan/2026-09-23-1500_571a-w3-personas-responsive-audit.md` gerendert
// belegt (Chromium gegen das gebaute CSS, 320/375/768/1024 px).
describe('PersonaProfileEditor — Responsive (#571)', () => {
  it('bricht Profil-Inhalt an Bezeichnern ohne Trennstelle um', () => {
    render(<PersonaProfileEditor />)

    // Gemessen bei 320 px: der Container zeigte 371 px Inhalt in 236 px
    // sichtbarer Breite. Ein Persona-Profil traegt fremdbestimmte Bezeichner
    // (Playbook-/Resource-Namen, Tool-Aliasse) ohne Trennstelle; die Klasse
    // vererbt an alle Nachkommen und deckt damit auch Inhalte ab, die erst
    // zur Laufzeit entstehen (Muster wie §11 „break-words am <main>").
    const container = screen.getByTestId('persona-profile-editor')
    expect(container).toHaveClass('break-words')
  })
})
