import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Token } from '@/api/types'

import { AgentTokensSection } from './AgentTokensSection'

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

// Stabiles `api`-Objekt (gleiche Referenz ueber alle Renders) — sonst rerendert
// der useCallback-Loader von useListData endlos und die Liste laedt nie.
const mocks = vi.hoisted(() => {
  const listTokens = vi.fn()
  const createToken = vi.fn()
  const renameToken = vi.fn()
  const rotateToken = vi.fn()
  const revokeToken = vi.fn()
  return {
    listTokens,
    createToken,
    renameToken,
    rotateToken,
    revokeToken,
    api: { listTokens, createToken, renameToken, rotateToken, revokeToken },
  }
})

vi.mock('@/api/useApi', () => ({ useApi: () => mocks.api }))

function makeToken(overrides: Partial<Token> = {}): Token {
  return {
    id: 't-1',
    workspace_id: 'ws-1',
    name: 'CI',
    agent_id: 'a-1',
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: null,
    revoked_at: null,
    ...overrides,
  }
}

beforeEach(() => {
  mocks.listTokens.mockReset().mockResolvedValue([makeToken()])
  mocks.createToken.mockReset()
  mocks.renameToken.mockReset()
  mocks.rotateToken.mockReset()
  mocks.revokeToken.mockReset()
})

describe('AgentTokensSection', () => {
  it('erstellt einen agent-gebundenen Token und zeigt das Secret einmalig', async () => {
    mocks.createToken.mockResolvedValue({ ...makeToken({ id: 't-new' }), token: 'w2b_neu_secret' })
    render(<AgentTokensSection agentId="a-1" />)
    await waitFor(() => expect(screen.getByText('CI')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Mein Token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Anlegen' }))

    await waitFor(() =>
      expect(mocks.createToken).toHaveBeenCalledWith({
        name: 'Mein Token',
        role: 'editor',
        agent_id: 'a-1',
      }),
    )
    expect((screen.getByLabelText('Klartext-Token') as HTMLTextAreaElement).value).toBe(
      'w2b_neu_secret',
    )
  })

  it('rotiert einen Token und zeigt das neue Secret', async () => {
    mocks.rotateToken.mockResolvedValue({ ...makeToken(), token: 'w2b_rotated' })
    render(<AgentTokensSection agentId="a-1" />)
    await waitFor(() => expect(screen.getByText('CI')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Rotieren' }))

    await waitFor(() => expect(mocks.rotateToken).toHaveBeenCalledWith('t-1'))
    await waitFor(() =>
      expect((screen.getByLabelText('Klartext-Token') as HTMLTextAreaElement).value).toBe(
        'w2b_rotated',
      ),
    )
  })

  it('benennt einen Token inline um', async () => {
    mocks.renameToken.mockResolvedValue(makeToken({ name: 'neu' }))
    render(<AgentTokensSection agentId="a-1" />)
    await waitFor(() => expect(screen.getByText('CI')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Umbenennen' }))
    fireEvent.change(screen.getByLabelText('Neuer Token-Name'), { target: { value: 'neu' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() => expect(mocks.renameToken).toHaveBeenCalledWith('t-1', { name: 'neu' }))
  })

  it('deaktiviert die Aktionen fuer widerrufene Tokens', async () => {
    mocks.listTokens.mockResolvedValue([makeToken({ revoked_at: '2026-02-01T00:00:00Z' })])
    render(<AgentTokensSection agentId="a-1" />)
    await waitFor(() => expect(screen.getByText('CI')).toBeInTheDocument())

    expect(screen.getByRole('button', { name: 'Widerrufen' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Rotieren' })).toBeDisabled()
  })
})
