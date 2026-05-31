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
