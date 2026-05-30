import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { Persona, SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'

import { AgentEditorForm } from '../components/AgentEditorForm'
import { AgentHierarchyView } from '../components/AgentHierarchyView'
import { CopyPromptButton } from '../components/CopyPromptButton'
import { useAgent } from '../hooks/useAgent'
import { useAgentForm } from '../hooks/useAgentForm'

export function AgentDetailPage() {
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
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/agents')}>
            <ArrowLeft className="h-4 w-4" />
            Agents
          </Link>
        </Button>
        <DataView loading={loading && agent === null} error={error}>
          {agent !== null ? (
            <Stack gap="lg">
              <Stack gap="md">
                <PageHeader
                  title={agent.name}
                  description={agent.description || undefined}
                  actions={
                    <CopyPromptButton
                      agentId={agent.id}
                      disabled={agent.status !== 'enabled'}
                    />
                  }
                />
              </Stack>

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
                submitLabel="Speichern"
              />
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
