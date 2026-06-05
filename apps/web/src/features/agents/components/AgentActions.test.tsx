import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent } from '@/api/types'

import { DeleteAgentButton } from './DeleteAgentButton'
import { DuplicateAgentButton } from './DuplicateAgentButton'

const copyAgent = vi.fn()
const deleteAgent = vi.fn()
const navigate = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()
let role: string = 'editor'

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ copyAgent, deleteAgent }),
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'a-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Carla',
    description: '',
    persona_id: 'p-1',
    system_prompt_template_id: 't-1',
    status: 'enabled',
    tool_policy: DEFAULT_TOOL_POLICY,
    persona_active: true,
    activatable: true,
    missing: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

// Radix Dialog nutzt PointerCapture-APIs, die jsdom nicht kennt.
beforeAll(() => {
  for (const fn of ['hasPointerCapture', 'releasePointerCapture', 'setPointerCapture', 'scrollIntoView'] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
})

beforeEach(() => {
  copyAgent.mockReset()
  deleteAgent.mockReset()
  navigate.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  role = 'editor'
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('DuplicateAgentButton', () => {
  it('dupliziert einen vollständigen Agent und navigiert zur Kopie', async () => {
    copyAgent.mockResolvedValue(makeAgent({ id: 'a-2', name: 'Carla (Kopie)' }))
    render(<DuplicateAgentButton agent={makeAgent()} />)

    const button = screen.getByTestId('duplicate-agent')
    expect(button).toBeEnabled()
    fireEvent.click(button)

    await waitFor(() => {
      expect(copyAgent).toHaveBeenCalledWith('a-1')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/agents/a-2')
    })
  })

  it('ist ausgegraut für einen nicht aktivierbaren Agent', () => {
    render(
      <DuplicateAgentButton
        agent={makeAgent({ persona_id: null, activatable: false, missing: ['persona'] })}
      />,
    )
    const button = screen.getByTestId('duplicate-agent')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', expect.stringContaining('Persona verknüpfen'))
    fireEvent.click(button)
    expect(copyAgent).not.toHaveBeenCalled()
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DuplicateAgentButton agent={makeAgent()} />)
    expect(screen.getByTestId('duplicate-agent')).toBeDisabled()
  })
})

describe('DeleteAgentButton', () => {
  it('löscht nach Bestätigung und navigiert zur Liste', async () => {
    deleteAgent.mockResolvedValue(undefined)
    render(<DeleteAgentButton agent={makeAgent()} />)

    fireEvent.click(screen.getByTestId('delete-agent-trigger'))
    const confirm = await screen.findByTestId('delete-agent-confirm')
    fireEvent.click(confirm)

    await waitFor(() => {
      expect(deleteAgent).toHaveBeenCalledWith('a-1')
      expect(navigate).toHaveBeenCalledWith('/w/ws-1/agents')
    })
  })

  it('ist für Viewer ausgegraut', () => {
    role = 'viewer'
    render(<DeleteAgentButton agent={makeAgent()} />)
    expect(screen.getByTestId('delete-agent-trigger')).toBeDisabled()
  })
})
