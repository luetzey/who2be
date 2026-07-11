import { fireEvent, render, screen } from '@testing-library/react'
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

function Harness({ agent, locked }: { agent: Agent; locked?: boolean }) {
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
      tg_persona_promote: agent.tool_policy.transition_grants?.persona?.promote ?? true,
      tg_persona_retire: agent.tool_policy.transition_grants?.persona?.retire ?? true,
      tg_playbook_promote: agent.tool_policy.transition_grants?.playbook?.promote ?? true,
      tg_playbook_retire: agent.tool_policy.transition_grants?.playbook?.retire ?? true,
      tg_resource_promote: agent.tool_policy.transition_grants?.resource?.promote ?? true,
      tg_resource_retire: agent.tool_policy.transition_grants?.resource?.retire ?? true,
      write_rate_limit:
        agent.tool_policy.write_rate_limit != null
          ? String(agent.tool_policy.write_rate_limit)
          : '',
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
      locked={locked}
    />
  )
}

// Policy-Felder liegen im Tab „Werkzeuge & Rechte" (per Default nicht gemountet).
function openToolsTab() {
  fireEvent.click(screen.getByRole('tab', { name: 'Werkzeuge & Rechte' }))
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
    openToolsTab()

    // Read-Scope-Select fuer Playbooks (Default-Policy: alle).
    expect(screen.getByLabelText('Playbooks lesen')).toBeInTheDocument()
    // Eine Write-Capability-Checkbox ist vorhanden und per Default aus.
    const playbookWrite = screen.getByLabelText('Playbooks erstellen/ändern/verknüpfen')
    expect(playbookWrite).not.toBeChecked()
    // ADR-0040/0038: System-Prompt- + Feedback-Capability sind im Editor sichtbar;
    // Feedback ist secure-by-default AN, System-Prompt aus.
    expect(screen.getByLabelText('System-Prompts verfassen (Review einreichen)')).not.toBeChecked()
    expect(screen.getByLabelText('Nutzung/Feedback melden')).toBeChecked()
    // Feedback-Triage (Signale schliessen) ist secure-by-default AUS.
    expect(
      screen.getByLabelText('Feedback-Triage: Signale schließen (addressed/in_progress/dismissed)'),
    ).not.toBeChecked()
  })

  it('zeigt den write_tags-Tag-Scope pro Domain (ADR-0039)', () => {
    const agent = makeAgent({
      tool_policy: { ...DEFAULT_TOOL_POLICY, write_tags: { playbook: ['support', 'billing'] } },
    })
    render(<Harness agent={agent} />)
    openToolsTab()
    // Playbook-Tag-Feld traegt die erlaubten Tags; Persona bleibt leer (= alle).
    expect(screen.getByLabelText('Playbook-Tags')).toHaveValue('support, billing')
    expect(screen.getByLabelText('Persona-Tags')).toHaveValue('')
  })

  it('sperrt alle Felder + Speichern, wenn vom System verwaltet (locked)', () => {
    render(
      <Harness
        agent={makeAgent({
          persona_id: 'p-1',
          system_prompt_template_id: 't-1',
          persona_active: true,
          activatable: true,
          missing: [],
          is_managed: true,
        })}
        locked
      />,
    )

    // Konfiguration-Tab (Default): Name + Speichern gesperrt.
    expect(screen.getByLabelText('Name')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled()
    // Werkzeuge-&-Rechte-Tab: Policy-Felder + Speichern ebenfalls gesperrt.
    openToolsTab()
    expect(screen.getByLabelText('Playbooks lesen')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled()
  })

  it('spiegelt transition_grants als per-Domain Promote/Retire (ADR-0039)', () => {
    const agent = makeAgent({
      tool_policy: {
        ...DEFAULT_TOOL_POLICY,
        promote_retire: true,
        transition_grants: { playbook: { promote: true, retire: false } },
      },
    })
    render(<Harness agent={agent} />)
    openToolsTab()
    // Playbook: promoten erlaubt, retiren abgewaehlt; Persona ohne Eintrag = beide an.
    const promotes = screen.getAllByLabelText('Promoten (→ aktiv)')
    const retires = screen.getAllByLabelText('Zurückziehen (→ inaktiv)')
    // Reihenfolge: persona, playbook, resource.
    expect(promotes[1]).toBeChecked()
    expect(retires[1]).not.toBeChecked()
    expect(promotes[0]).toBeChecked()
    expect(retires[0]).toBeChecked()
  })
})
