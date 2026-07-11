import { Bot } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useParams } from 'react-router-dom'

import type { Agent, Persona, SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'

import { AgentConnectorSection } from '../components/AgentConnectorSection'
import { AgentEditorForm } from '../components/AgentEditorForm'
import { AgentHierarchyView } from '../components/AgentHierarchyView'
import { AgentTokensSection } from '../components/AgentTokensSection'
import { CopyPromptButton } from '../components/CopyPromptButton'
import { DeleteAgentButton } from '../components/DeleteAgentButton'
import { DuplicateAgentButton } from '../components/DuplicateAgentButton'
import { useAgent } from '../hooks/useAgent'
import { useAgentForm } from '../hooks/useAgentForm'

// Agent-Status als bordered Capsule fuer den Detail-Header (Design-Handoff
// „Detail-Redesign"). Unvollstaendig hat Vorrang; Farbe aus `--status-*`,
// nie als alleiniges Signal (Punkt + Label, design-language §11).
function AgentStatusBadge({ agent }: { agent: Agent }) {
  const { t } = useTranslation('agents')
  const { token, label } = !agent.activatable
    ? { token: 'draft', label: t('status.incomplete') }
    : agent.status === 'enabled'
      ? { token: 'active', label: t('status.enabled') }
      : { token: 'inactive', label: t('status.disabled') }

  return (
    <span className="inline-flex items-center gap-2 rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground">
      <span
        className="inline-block size-2 rounded-full"
        style={{ backgroundColor: `var(--status-${token})` }}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

export function AgentDetailPage() {
  const { t } = useTranslation('agents')
  const { id } = useParams<{ id: string }>()
  const wsPath = useWorkspacePath()
  const api = useApi()
  const { agent, persona, template, playbooks, loading, error, reload } = useAgent(id)
  const { form, onSubmit, saveError } = useAgentForm(agent, reload)
  const [personas, setPersonas] = useState<Persona[]>([])
  const [templates, setTemplates] = useState<SystemPromptTemplate[]>([])

  useEffect(() => {
    void Promise.all([api.listPersonas(), api.listSystemPromptTemplates()]).then(
      ([loadedPersonas, loadedTemplates]) => {
        setPersonas(loadedPersonas)
        setTemplates(loadedTemplates)
      },
    )
  }, [api])

  if (id === undefined) {
    return <Navigate to={wsPath('/agents')} replace />
  }

  return (
    <Container>
      <DataView loading={loading && agent === null} error={error}>
        {agent !== null ? (
          (() => {
            const locked = agent.is_managed === true
            return (
              <Stack gap="lg">
                <DetailHeader
                  icon={Bot}
                  iconTone="catalog"
                  backHref={wsPath('/agents')}
                  backLabel={t('detail.back')}
                  title={agent.name}
                  badges={<AgentStatusBadge agent={agent} />}
                  description={agent.description || undefined}
                  actions={
                    <>
                      <CopyPromptButton
                        agentId={agent.id}
                        disabled={agent.status !== 'enabled'}
                      />
                      <DuplicateAgentButton agent={agent} />
                      {locked ? null : <DeleteAgentButton agent={agent} />}
                    </>
                  }
                />
                {locked ? <ManagedNotice showDuplicateHint /> : null}

                <AgentHierarchyView
                  agent={agent}
                  persona={persona}
                  template={template}
                  playbooks={playbooks}
                />

                <AgentEditorForm
                  form={form}
                  onSubmit={onSubmit}
                  saveError={saveError}
                  personas={personas}
                  templates={templates}
                  agent={agent}
                  locked={locked}
                  connectionSlot={
                    <Stack gap="lg">
                      <AgentConnectorSection agentId={agent.id} agentName={agent.name} />
                      <AgentTokensSection agentId={agent.id} />
                    </Stack>
                  }
                />
              </Stack>
            )
          })()
        ) : null}
      </DataView>
    </Container>
  )
}
