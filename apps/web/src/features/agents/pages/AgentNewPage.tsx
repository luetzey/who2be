import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import type { Persona, SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

import { AgentEditorForm } from '../components/AgentEditorForm'
import type { AgentEditorValues } from '../hooks/useAgentForm'

const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  persona_id: z.string().min(1, 'Persona erforderlich.'),
  system_prompt_template_id: z.string().min(1, 'Systemprompt erforderlich.'),
  status: z.enum(['enabled', 'disabled']),
})

export function AgentNewPage() {
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [templates, setTemplates] = useState<SystemPromptTemplate[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<AgentEditorValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: '',
      description: '',
      persona_id: '',
      system_prompt_template_id: '',
      status: 'enabled',
    },
  })

  useEffect(() => {
    setLoading(true)
    setLoadError(null)
    void Promise.all([api.listPersonas(), api.listSystemPromptTemplates()])
      .then(([loadedPersonas, loadedTemplates]) => {
        setPersonas(loadedPersonas)
        setTemplates(loadedTemplates)
      })
      .catch((cause: unknown) => {
        setLoadError(cause instanceof Error ? cause.message : 'Daten konnten nicht geladen werden.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [api])

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createAgent({
        name: values.name,
        description: values.description,
        persona_id: values.persona_id,
        system_prompt_template_id: values.system_prompt_template_id,
        status: values.status,
      })
      notify.success('Agent angelegt.')
      navigate(wsPath(`/agents/${created.id}`))
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : 'Unbekannter Fehler.')
    }
  })

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/agents')}>
            <ArrowLeft className="h-4 w-4" />
            Agents
          </Link>
        </Button>
        <PageHeader title="Neuer Agent" description="Verknüpfe Persona und Systemprompt." />

        {loading ? (
          <LoadingState />
        ) : loadError !== null ? (
          <ErrorAlert message={loadError} />
        ) : personas.length === 0 ? (
          <EmptyState
            title="Keine Persona vorhanden."
            description="Du brauchst zuerst eine Persona, um einen Agent anzulegen."
            action={
              <Button asChild variant="brand">
                <Link to={wsPath('/personas/new')}>Persona anlegen</Link>
              </Button>
            }
          />
        ) : (
          <AgentEditorForm
            form={form}
            onSubmit={onSubmit}
            saveError={saveError}
            personas={personas}
            templates={templates}
            submitLabel="Anlegen"
          />
        )}
      </Stack>
    </Container>
  )
}
