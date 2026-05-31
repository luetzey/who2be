import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'

import { SessionContext } from './session-context'
import { useWorkspaceId } from './useWorkspaceId'

function Probe() {
  const wsId = useWorkspaceId()
  return <span data-testid="ws">{wsId === '' ? '<none>' : wsId}</span>
}

function wrap(children: ReactNode, me: Me | null, initialPath: string, pattern: string) {
  return (
    <SessionContext.Provider
      value={{ session: null, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={pattern} element={children} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>
  )
}

describe('useWorkspaceId', () => {
  it('liest die Workspace-ID aus dem Route-Param', () => {
    render(wrap(<Probe />, null, '/w/abc-123/personas', '/w/:workspaceId/personas'))
    expect(screen.getByTestId('ws').textContent).toBe('abc-123')
  })

  it('faellt auf die default_workspace_id aus /me zurueck', () => {
    const me: Me = {
      user_id: 'u1',
      default_workspace_id: 'default-ws',
      organizations: [],
    }
    render(wrap(<Probe />, me, '/login', '/login'))
    expect(screen.getByTestId('ws').textContent).toBe('default-ws')
  })

  it('liefert leeren String ohne Route-Param und ohne /me', () => {
    render(wrap(<Probe />, null, '/login', '/login'))
    expect(screen.getByTestId('ws').textContent).toBe('<none>')
  })

  it('Route-Param hat Vorrang vor default_workspace_id', () => {
    const me: Me = {
      user_id: 'u1',
      default_workspace_id: 'default-ws',
      organizations: [],
    }
    render(wrap(<Probe />, me, '/w/route-ws/personas', '/w/:workspaceId/personas'))
    expect(screen.getByTestId('ws').textContent).toBe('route-ws')
  })
})
