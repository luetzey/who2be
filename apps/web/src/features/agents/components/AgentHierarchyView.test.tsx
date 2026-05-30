import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type {
  Agent,
  Persona,
  Playbook,
  SystemPromptTemplate,
} from '@/api/types'

import { AgentHierarchyView } from './AgentHierarchyView'

function mockAgent(): Agent {
  return {
    id: 'agent-1',
    workspace_id: 'ws',
    owner_id: 'u',
    name: 'Coach Carla Bot',
    description: 'Coach Carla als Customer-Support-Agent',
    persona_id: 'p',
    system_prompt_template_id: 't',
    status: 'enabled',
    created_at: '2026-05-30T10:00:00Z',
    updated_at: '2026-05-30T10:00:00Z',
  }
}

function mockPersona(): Persona {
  return {
    id: 'p',
    workspace_id: 'ws',
    owner_id: 'u',
    name: 'Coach Carla',
    current_version: 3,
    content: {
      description: 'Senior-Coach',
      system_prompt: '',
      traits: [],
      tags: [],
    },
    created_at: 't',
    updated_at: 't',
  }
}

function mockTemplate(): SystemPromptTemplate {
  return {
    id: 't',
    workspace_id: 'ws',
    owner_id: 'u',
    name: 'Customer-Support-Agent',
    slug: 'customer-support-agent',
    current_version: 1,
    content: { description: '', body: 'Du bist {{ persona.name }}' },
    created_at: 't',
    updated_at: 't',
  }
}

function mockPlaybooks(): Playbook[] {
  return [
    {
      id: 'pb1',
      workspace_id: 'ws',
      owner_id: 'u',
      name: 'Reset-Mail',
      current_version: 2,
      type: 'prompt',
      tags: [],
      triggers: null,
      content: {
        description: '',
        body: '',
        type: 'prompt',
        tags: [],
        triggers: null,
      },
      created_at: 't',
      updated_at: 't',
    },
    {
      id: 'pb2',
      workspace_id: 'ws',
      owner_id: 'u',
      name: 'Eskalation',
      current_version: 1,
      type: 'prompt',
      tags: [],
      triggers: null,
      content: {
        description: '',
        body: '',
        type: 'prompt',
        tags: [],
        triggers: null,
      },
      created_at: 't',
      updated_at: 't',
    },
  ]
}

describe('AgentHierarchyView', () => {
  it('rendert Agent-Name, Persona, Template und Playbook-Liste', () => {
    render(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={mockPersona()}
        template={mockTemplate()}
        playbooks={mockPlaybooks()}
      />,
    )
    expect(screen.getByText('Coach Carla Bot')).toBeInTheDocument()
    expect(screen.getByText('Coach Carla')).toBeInTheDocument()
    expect(screen.getByText('Customer-Support-Agent')).toBeInTheDocument()
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(2)
    expect(screen.getByText('Reset-Mail')).toBeInTheDocument()
    expect(screen.getByText('Eskalation')).toBeInTheDocument()
  })

  it('zeigt Status-Badge "Aktiv" fuer enabled', () => {
    render(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={null}
        template={null}
        playbooks={[]}
      />,
    )
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
  })

  it('zeigt "Keine Playbooks verknüpft." wenn die Liste leer ist', () => {
    render(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={mockPersona()}
        template={mockTemplate()}
        playbooks={[]}
      />,
    )
    expect(screen.getByText('Keine Playbooks verknüpft.')).toBeInTheDocument()
  })
})
