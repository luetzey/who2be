import { render, screen } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'

import type { Agent, Persona, SystemPromptTemplate } from '@/api/types'

import { AgentEditorForm } from './AgentEditorForm'
import type { AgentEditorValues } from '../hooks/useAgentForm'

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'a-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Carla',
    description: '',
    persona_id: null,
    system_prompt_template_id: null,
    status: 'disabled',
    persona_active: false,
    activatable: false,
    missing: ['persona', 'template', 'persona_active'],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const personas: Persona[] = []
const templates: SystemPromptTemplate[] = []

function Harness({ agent }: { agent: Agent }) {
  const form = useForm<AgentEditorValues>({
    defaultValues: {
      name: agent.name,
      description: agent.description,
      persona_id: agent.persona_id ?? '',
      system_prompt_template_id: agent.system_prompt_template_id ?? '',
      status: agent.status,
    },
  })
  return (
    <AgentEditorForm
      form={form}
      onSubmit={async () => {}}
      saveError={null}
      personas={personas}
      templates={templates}
      agent={agent}
    />
  )
}

describe('AgentEditorForm', () => {
  it('zeigt die fehlenden Punkte und sperrt „Aktiv" bei nicht aktivierbarem Agent', () => {
    render(<Harness agent={makeAgent()} />)

    const notice = screen.getByTestId('agent-missing-notice')
    expect(notice).toHaveTextContent('Persona verknüpfen')
    expect(notice).toHaveTextContent('Systemprompt verknüpfen')
    expect(notice).toHaveTextContent('verknüpfte Persona aktiv schalten')

    expect(screen.getByRole('option', { name: 'Aktiv' })).toBeDisabled()
  })

  it('erlaubt „Aktiv" und blendet den Hinweis aus, wenn aktivierbar', () => {
    render(
      <Harness
        agent={makeAgent({
          persona_id: 'p-1',
          system_prompt_template_id: 't-1',
          persona_active: true,
          activatable: true,
          missing: [],
        })}
      />,
    )

    expect(screen.queryByTestId('agent-missing-notice')).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Aktiv' })).toBeEnabled()
  })
})
