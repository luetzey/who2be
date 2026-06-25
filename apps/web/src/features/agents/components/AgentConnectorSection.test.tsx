import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentConnectorSection } from './AgentConnectorSection'

const notifySuccess = vi.fn()
const notifyError = vi.fn()
const writeText = vi.fn()

vi.mock('@/config', () => ({
  config: { mcpUrl: 'https://mcp.example.com/mcp' },
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

beforeEach(() => {
  notifySuccess.mockReset()
  notifyError.mockReset()
  writeText.mockReset()
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AgentConnectorSection', () => {
  it('baut eine pro Agent eindeutige Connector-URL mit ?agent=<id>', () => {
    render(<AgentConnectorSection agentId="abc-123" agentName="Coder" />)
    expect(screen.getByDisplayValue('https://mcp.example.com/mcp?agent=abc-123')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Who2Be – Coder')).toBeInTheDocument()
  })

  it('kopiert die URL in die Zwischenablage und meldet Erfolg', async () => {
    writeText.mockResolvedValue(undefined)
    render(<AgentConnectorSection agentId="abc-123" agentName="Coder" />)

    fireEvent.click(screen.getByRole('button', { name: 'URL kopieren' }))

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith('https://mcp.example.com/mcp?agent=abc-123'),
    )
    expect(notifySuccess).toHaveBeenCalledWith('In Zwischenablage kopiert.')
  })
})
