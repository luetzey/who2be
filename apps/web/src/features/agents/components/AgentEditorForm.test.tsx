import { render, screen } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent, type Persona, type SystemPromptTemplate } from '@/api/types'

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
    tool_policy: DEFAULT_TOOL_POLICY,
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
      ...agent.tool_policy,
      write_tags_persona: (agent.tool_policy.write_tags?.persona ?? []).join(', '),
      write_tags_playbook: (agent.tool_policy.write_tags?.playbook ?? []).join(', '),
      write_tags_resource: (agent.tool_policy.write_tags?.resource ?? []).join(', '),
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

  it('rendert die Werkzeuge-&-Rechte-Sektion mit Read-Scopes und Write-Switches', () => {
    render(<Harness agent={makeAgent()} />)

    // Read-Scope-Select fuer Playbooks (Default-Policy: alle).
    expect(screen.getByLabelText('Playbooks lesen')).toBeInTheDocument()
    // Eine Write-Capability-Checkbox ist vorhanden und per Default aus.
    const playbookWrite = screen.getByLabelText('Playbooks erstellen/ändern/verknüpfen')
    expect(playbookWrite).not.toBeChecked()
    // ADR-0040/0038: System-Prompt- + Feedback-Capability sind im Editor sichtbar;
    // Feedback ist secure-by-default AN, System-Prompt aus.
    expect(screen.getByLabelText('System-Prompts verfassen (Review einreichen)')).not.toBeChecked()
    expect(screen.getByLabelText('Nutzung/Feedback melden')).toBeChecked()
  })

  it('zeigt den write_tags-Tag-Scope pro Domain (ADR-0039)', () => {
    const agent = makeAgent({
      tool_policy: { ...DEFAULT_TOOL_POLICY, write_tags: { playbook: ['support', 'billing'] } },
    })
    render(<Harness agent={agent} />)
    // Playbook-Tag-Feld traegt die erlaubten Tags; Persona bleibt leer (= alle).
    expect(screen.getByLabelText('Playbook-Tags')).toHaveValue('support, billing')
    expect(screen.getByLabelText('Persona-Tags')).toHaveValue('')
  })
})
