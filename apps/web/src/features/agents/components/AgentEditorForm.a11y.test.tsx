import { render } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent, type Persona, type SystemPromptTemplate } from '@/api/types'
import { axe } from '@/test/a11y'

import { AgentEditorForm } from './AgentEditorForm'
import type { AgentEditorValues } from '../hooks/useAgentForm'

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

const agent: Agent = {
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
}

const personas: Persona[] = []
const templates: SystemPromptTemplate[] = []

function Harness() {
  const form = useForm<AgentEditorValues>({
    defaultValues: {
      name: agent.name,
      description: agent.description,
      persona_id: '',
      system_prompt_template_id: '',
      status: agent.status,
      ...agent.tool_policy,
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

describe('AgentEditorForm (a11y)', () => {
  it('hat keine axe-Violations inkl. der Werkzeuge-&-Rechte-Sektion', async () => {
    const { container } = render(<Harness />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
