import { Bot, FilePlus2, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

import { useAgents } from '../hooks/useAgents'
import { isAgentShell } from '../lib/shell'

export function AgentsPage() {
  const { agents, loading, error } = useAgents()
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [creatingShell, setCreatingShell] = useState(false)

  const createShell = async () => {
    setCreatingShell(true)
    try {
      const created = await api.createAgent({ name: 'Neuer Agent' })
      notify.success('Leerer Agent angelegt — jetzt Persona und Systemprompt zuweisen.')
      navigate(wsPath(`/agents/${created.id}`))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
      setCreatingShell(false)
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Agents"
          description="Konfigurierte Agents — Persona × Template, einmal klicken zum Kopieren."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={isViewer || creatingShell}
                onClick={() => void createShell()}
                title={isViewer ? 'Viewer können keine Agents anlegen' : undefined}
                data-testid="new-empty-agent"
              >
                <FilePlus2 className="h-4 w-4" />
                Neuer leerer Agent
              </Button>
              <Button asChild variant="brand">
                <Link to={wsPath('/agents/new')}>
                  <Plus className="h-4 w-4" />
                  Neuer Agent
                </Link>
              </Button>
            </div>
          }
        />
        <DataList
          items={agents}
          loading={loading}
          error={error}
          getKey={(agent) => agent.id}
          empty={
            <EmptyState
              icon={Bot}
              title="Noch keine Agents"
              description="Lege deinen ersten Agent an, um Prompts mit einem Klick zu kopieren."
              action={
                <Button asChild variant="brand">
                  <Link to={wsPath('/agents/new')}>
                    <Plus className="h-4 w-4" />
                    Neuer Agent
                  </Link>
                </Button>
              }
            />
          }
          renderItem={(agent) => (
            <div className="flex items-center justify-between gap-3">
              <Link
                to={wsPath(`/agents/${agent.id}`)}
                className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                {agent.name}
              </Link>
              <div className="flex items-center gap-2">
                {isAgentShell(agent) ? <Badge variant="outline">Hülle</Badge> : null}
                <Badge variant={agent.status === 'enabled' ? 'default' : 'outline'}>
                  {agent.status === 'enabled' ? 'Aktiv' : 'Deaktiviert'}
                </Badge>
              </div>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
