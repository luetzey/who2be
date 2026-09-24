import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { CopyPromptButton } from './CopyPromptButton'

const renderAgentPrompt = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
const notifyInfo = vi.fn()
const writeText = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ renderAgentPrompt }),
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: (...args: unknown[]) => notifyInfo(...args),
  },
}))

// Radix DropdownMenu nutzt PointerCapture- und scrollIntoView-APIs, die jsdom
// nicht implementiert. Stub-Polyfill, damit Trigger + Items aktivierbar sind.
beforeAll(() => {
  Object.defineProperty(window.HTMLElement.prototype, 'hasPointerCapture', {
    value: () => false,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'releasePointerCapture', {
    value: () => undefined,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'setPointerCapture', {
    value: () => undefined,
    configurable: true,
  })
  Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
    value: () => undefined,
    configurable: true,
  })
})

beforeEach(() => {
  renderAgentPrompt.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  notifyInfo.mockReset()
  writeText.mockReset()
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function openDropdown() {
  const trigger = screen.getByTestId('copy-prompt-dropdown-trigger')
  // Radix oeffnet auf pointerdown+up; in jsdom kommen wir per Enter ans Ziel.
  fireEvent.keyDown(trigger, { key: 'Enter' })
}

describe('CopyPromptButton', () => {
  it('Primary-Click rendert plain und kopiert in die Zwischenablage', async () => {
    renderAgentPrompt.mockResolvedValueOnce({
      content: 'PLAIN-PROMPT',
      unresolved_placeholders: [],
      format: 'plain',
    })
    writeText.mockResolvedValue(undefined)
    render(<CopyPromptButton agentId="a1" />)

    fireEvent.click(screen.getByTestId('copy-prompt-primary'))

    await waitFor(() => expect(renderAgentPrompt).toHaveBeenCalledWith('a1', 'plain'))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('PLAIN-PROMPT'))
    expect(notifySuccess).toHaveBeenCalledWith('Prompt in Zwischenablage.')
  })

  it('Dropdown "Als Markdown kopieren" loest format=markdown aus', async () => {
    renderAgentPrompt.mockResolvedValueOnce({
      content: '## MD',
      unresolved_placeholders: [],
      format: 'markdown',
    })
    writeText.mockResolvedValue(undefined)
    render(<CopyPromptButton agentId="a1" />)

    openDropdown()
    const item = await screen.findByRole('menuitem', { name: /Als Markdown kopieren/ })
    fireEvent.click(item)

    await waitFor(() =>
      expect(renderAgentPrompt).toHaveBeenCalledWith('a1', 'markdown'),
    )
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('## MD'))
  })

  it('Dropdown "Als HTML kopieren" loest format=html aus', async () => {
    renderAgentPrompt.mockResolvedValueOnce({
      content: '<h2>HTML</h2>',
      unresolved_placeholders: [],
      format: 'html',
    })
    writeText.mockResolvedValue(undefined)
    render(<CopyPromptButton agentId="a1" />)

    openDropdown()
    const item = await screen.findByRole('menuitem', { name: /Als HTML kopieren/ })
    fireEvent.click(item)

    await waitFor(() =>
      expect(renderAgentPrompt).toHaveBeenCalledWith('a1', 'html'),
    )
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('<h2>HTML</h2>'))
  })

  it('zeigt Hinweis-Toast bei unresolved placeholders', async () => {
    renderAgentPrompt.mockResolvedValueOnce({
      content: 'X ⚠ {{ xyz }}',
      unresolved_placeholders: ['xyz'],
      format: 'plain',
    })
    writeText.mockResolvedValue(undefined)
    render(<CopyPromptButton agentId="a1" />)
    fireEvent.click(screen.getByTestId('copy-prompt-primary'))
    await waitFor(() => expect(notifyInfo).toHaveBeenCalled())
    expect(notifyInfo.mock.calls[0][0]).toContain('xyz')
  })

  it('disabled-Prop deaktiviert primary + dropdown', () => {
    render(<CopyPromptButton agentId="a1" disabled />)
    expect(screen.getByTestId('copy-prompt-primary')).toBeDisabled()
    expect(screen.getByTestId('copy-prompt-dropdown-trigger')).toBeDisabled()
  })
})

// Responsive-Vertrag #570 (AK 4): der Dropdown-Teil des Split-Buttons traegt
// nur ein Chevron und war deshalb schmaler als hoch. Die Zahl 40 px kommt aus
// AK 4 dieses Issues, nicht aus der Norm: `docs/frontend/design-language.md`
// §11 ist die einzige Quelle des Floors und setzt ihn auf >= 32 px — die
// gemessenen 33 px Breite lagen knapp darueber, 40 px ist dort die Praeferenz
// `size="default"`, die dieses Paket unterhalb `md` verbindlich macht.
//
// Gemessen am gebauten Stylesheet in Chromium bei 320 px: `px-2` um ein 16-px-
// Icon ergibt 33 px Breite bei 40 px Hoehe — ein Hit-Target, das in einer
// Achse unter dem Regelfall bleibt. `w-10` macht daraus 40x40 px; ab `md`
// gibt `md:w-auto` die Desktop-Dichte wieder frei.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1600_570-w3-agents-haelfte-b-responsive-audit.md
// gerendert belegt (33x40 -> 40x40 px).
describe('CopyPromptButton — Responsive (#570)', () => {
  it('haelt am Dropdown-Trigger den 40-px-Hit-Target aus AK 4 unterhalb md und gibt ihn ab md wieder frei', () => {
    render(<CopyPromptButton agentId="a1" />)

    const trigger = screen.getByTestId('copy-prompt-dropdown-trigger')
    expect(trigger).toHaveClass('w-10')
    expect(trigger).toHaveClass('md:w-auto')
  })
})
