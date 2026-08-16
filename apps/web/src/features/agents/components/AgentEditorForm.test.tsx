import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_TOOL_POLICY,
  type Agent,
  type AgentToolPolicy,
  type Persona,
  type SystemPromptTemplate,
  type WorkspaceRole,
} from '@/api/types'

import { AgentEditorForm } from './AgentEditorForm'
import { useAgentForm } from '../hooks/useAgentForm'
import type { AgentEditorValues } from '../hooks/useAgentForm'

// Rolle ist pro Test umschaltbar (Viewer-Read-only-Fall). `vi.hoisted`, weil
// die vi.mock-Factory ueber die Modul-Variablen gehoisted wird.
const roleRef = vi.hoisted(() => ({ current: 'editor' as WorkspaceRole }))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => roleRef.current,
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Stabile Loader-Referenzen (Modul-Ebene) — der TagInput ruft sie beim Mount
// auf; neue Referenzen pro Render wuerden seinen useEffect endlos triggern.
const listPersonaTags = vi.fn().mockResolvedValue([])
const listPlaybookTags = vi.fn().mockResolvedValue([])
const listResourceTags = vi.fn().mockResolvedValue([])
// ADR-0044-Test: `updateAgent` faengt den PUT-Payload ab, um den
// memory_mode-Wert aus dem Formular zu verifizieren (useAgentForm-Muster).
const updateAgent = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ listPersonaTags, listPlaybookTags, listResourceTags, updateAgent }),
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
      write_tags_persona: agent.tool_policy.write_tags?.persona ?? [],
      write_tags_playbook: agent.tool_policy.write_tags?.playbook ?? [],
      write_tags_resource: agent.tool_policy.write_tags?.resource ?? [],
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
      // ADR-0047 Modell-Config: liegt am Agenten, nicht in der Policy.
      model_provider: agent.model_provider ?? '',
      model_name: agent.model_name ?? '',
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

// Nutzt den echten `useAgentForm`-Hook (statt der no-op-Harness oben), damit
// der PUT-Payload (inkl. `valuesToPolicy`-Merge) end-to-end pruefbar ist.
function FormHookHarness({ agent }: { agent: Agent }) {
  const { form, onSubmit } = useAgentForm(agent, () => {})
  return (
    <AgentEditorForm
      form={form}
      onSubmit={onSubmit}
      saveError={null}
      personas={personas}
      templates={templates}
      agent={agent}
    />
  )
}

afterEach(() => {
  roleRef.current = 'editor'
  updateAgent.mockReset()
})

// Submit ueber den Speichern-Button; jsdom feuert `submit` bei einem Klick auf
// den Submit-Button nicht selbst (Muster aus AgentDetailPage.test).
function submitEditor() {
  const submitButton = screen.getByRole('button', { name: 'Speichern' })
  fireEvent.click(submitButton)
  const formEl = submitButton.closest('form')
  if (formEl !== null) {
    fireEvent.submit(formEl)
  }
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
    // WP-3: ExternalTool-Read-Scope-Select (Default 'all') + Write-Switch
    // (Default aus) sind im Editor sichtbar — Muster identisch zu
    // playbook_read/system_prompt_write.
    expect(screen.getByLabelText('Externe Tools lesen')).toHaveValue('all')
    expect(screen.getByLabelText('Externe Tools erstellen/ändern')).not.toBeChecked()
    // Feedback-Triage (Signale schliessen) ist secure-by-default AUS.
    expect(
      screen.getByLabelText('Feedback-Triage: Signale schließen (addressed/in_progress/dismissed)'),
    ).not.toBeChecked()
  })

  it('zeigt den write_tags-Tag-Scope pro Domain als Pills (ADR-0039)', () => {
    const agent = makeAgent({
      tool_policy: { ...DEFAULT_TOOL_POLICY, write_tags: { playbook: ['support', 'billing'] } },
    })
    render(<Harness agent={agent} />)
    openToolsTab()
    // Playbook-Tag-Feld traegt die erlaubten Tags als entfernbare Pills; Persona
    // bleibt leer (= alle Tags), das Eingabefeld ist ein Combobox ohne Wert.
    expect(screen.getByLabelText('Tag support entfernen')).toBeInTheDocument()
    expect(screen.getByLabelText('Tag billing entfernen')).toBeInTheDocument()
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

  it('rendert die Gedächtnis-Sektion mit Default „Aus" und gesperrter Verbindlichkeit', () => {
    render(<Harness agent={makeAgent()} />)
    openToolsTab()

    expect(screen.getByLabelText('Speicher-Modus')).toHaveValue('off')
    // Verbindlichkeit ist erst ab mode != off wirksam — bei "Aus" gesperrt.
    expect(screen.getByLabelText('Verbindlichkeit')).toBeDisabled()
    expect(screen.getByLabelText('Verbindlichkeit')).toHaveValue('recommended')
  })

  it('submitted den memory_mode-Wert im PUT-Payload (ADR-0044)', async () => {
    const testAgent = makeAgent({
      persona_id: 'p-1',
      system_prompt_template_id: 't-1',
      persona_active: true,
      activatable: true,
      missing: [],
    })
    updateAgent.mockResolvedValue(testAgent)

    render(<FormHookHarness agent={testAgent} />)
    openToolsTab()

    fireEvent.change(screen.getByLabelText('Speicher-Modus'), {
      target: { value: 'suggest' },
    })
    // Erst ab mode != off editierbar.
    fireEvent.change(screen.getByLabelText('Verbindlichkeit'), {
      target: { value: 'required' },
    })

    const submitButton = screen.getByRole('button', { name: 'Speichern' })
    fireEvent.click(submitButton)
    const formEl = submitButton.closest('form')
    if (formEl !== null) {
      fireEvent.submit(formEl)
    }

    await waitFor(() => {
      expect(updateAgent).toHaveBeenCalled()
    })
    const payload = updateAgent.mock.calls[0]?.[1] as { tool_policy: { memory_mode: string; memory_directive: string } }
    expect(payload.tool_policy.memory_mode).toBe('suggest')
    expect(payload.tool_policy.memory_directive).toBe('required')
  })

  it('schaltet workarea_write frei und laesst die uebrige Policy unangetastet (ADR-0047)', async () => {
    // Bewusst eine vom Default abweichende Policy: so faellt auf, wenn der
    // Submit-Merge (`valuesToPolicy`) ein Feld verliert statt durchzureichen.
    const testAgent = makeAgent({
      tool_policy: {
        ...DEFAULT_TOOL_POLICY,
        playbook_read: 'all',
        promote_retire: true,
        write_tags: { playbook: ['support'] },
        transition_grants: { playbook: { promote: true, retire: false } },
        write_rate_limit: 5,
        memory_mode: 'suggest',
      },
    })
    updateAgent.mockResolvedValue(testAgent)

    render(<FormHookHarness agent={testAgent} />)
    openToolsTab()

    const workareaWrite = screen.getByLabelText(
      'Arbeitsbereich schreiben (Notizen, Ingest, Tabellen)',
    )
    expect(workareaWrite).not.toBeChecked()
    fireEvent.click(workareaWrite)
    expect(workareaWrite).toBeChecked()

    // Die beiden KB-Rechte sind eigenstaendig — der Arbeitsbereich schaltet sie
    // nicht mit frei (Kanten sind im MVP nicht loeschbar, ADR-0047).
    expect(
      screen.getByLabelText('Knowledge-Base-Aussagen anlegen/ändern (belegpflichtig)'),
    ).not.toBeChecked()
    expect(
      screen.getByLabelText('Knowledge-Base-Kanten anlegen (nicht mehr löschbar)'),
    ).not.toBeChecked()

    submitEditor()

    await waitFor(() => {
      expect(updateAgent).toHaveBeenCalled()
    })
    const payload = updateAgent.mock.calls[0]?.[1] as { tool_policy: AgentToolPolicy }
    expect(payload.tool_policy.workarea_write).toBe(true)
    expect(payload.tool_policy.kb_write).toBe(false)
    expect(payload.tool_policy.kb_edge_write).toBe(false)
    // Alles andere unveraendert durchgereicht.
    expect(payload.tool_policy.playbook_read).toBe('all')
    expect(payload.tool_policy.external_tool_read).toBe('all')
    expect(payload.tool_policy.persona_read).toBe(true)
    expect(payload.tool_policy.feedback_write).toBe(true)
    expect(payload.tool_policy.feedback_resolve).toBe(false)
    expect(payload.tool_policy.promote_retire).toBe(true)
    expect(payload.tool_policy.write_tags).toEqual({ playbook: ['support'] })
    expect(payload.tool_policy.transition_grants).toEqual({
      playbook: { promote: true, retire: false },
    })
    expect(payload.tool_policy.write_rate_limit).toBe(5)
    expect(payload.tool_policy.memory_mode).toBe('suggest')
  })

  it('laedt die Modell-Config und sendet das Leeren als leeren String mit (ADR-0047)', async () => {
    const testAgent = makeAgent({
      model_provider: 'anthropic',
      model_name: 'claude-opus-5',
    })
    updateAgent.mockResolvedValue(testAgent)

    render(<FormHookHarness agent={testAgent} />)

    const provider = screen.getByLabelText('Anbieter')
    const modelName = screen.getByLabelText('Modell')
    await waitFor(() => {
      expect(provider).toHaveValue('anthropic')
    })
    expect(modelName).toHaveValue('claude-opus-5')

    // Betreiber leert beide Felder (Anbieter nur mit Leerzeichen → getrimmt).
    fireEvent.change(provider, { target: { value: '   ' } })
    fireEvent.change(modelName, { target: { value: '' } })

    submitEditor()

    await waitFor(() => {
      expect(updateAgent).toHaveBeenCalled()
    })
    const payload = updateAgent.mock.calls[0]?.[1] as Record<string, unknown>
    // `''` heisst serverseitig "auf NULL leeren" — die Keys duerfen deshalb
    // NICHT weggelassen werden (sonst bliebe der falsche Anbieter stehen).
    expect(payload).toHaveProperty('model_provider', '')
    expect(payload).toHaveProperty('model_name', '')
  })

  it('sperrt Modell-Config und Arbeitsbereich-Rechte fuer Viewer', () => {
    roleRef.current = 'viewer'
    render(
      <Harness agent={makeAgent({ model_provider: 'anthropic', model_name: 'claude-opus-5' })} />,
    )

    expect(screen.getByLabelText('Anbieter')).toBeDisabled()
    expect(screen.getByLabelText('Modell')).toBeDisabled()

    openToolsTab()
    expect(
      screen.getByLabelText('Arbeitsbereich schreiben (Notizen, Ingest, Tabellen)'),
    ).toBeDisabled()
    expect(
      screen.getByLabelText('Knowledge-Base-Aussagen anlegen/ändern (belegpflichtig)'),
    ).toBeDisabled()
    expect(
      screen.getByLabelText('Knowledge-Base-Kanten anlegen (nicht mehr löschbar)'),
    ).toBeDisabled()
  })
})
