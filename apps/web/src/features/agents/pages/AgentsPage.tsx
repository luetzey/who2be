import { Bot, Plus } from 'lucide-react'
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

export function AgentsPage() {
  const { agents, loading, error } = useAgents()
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [creating, setCreating] = useState(false)

  // Genau ein Erstell-Pfad: ein leerer, sofort speicherbarer Agent. Persona,
  // Systemprompt und Status werden anschliessend in der Detail-Page ergaenzt.
  const createAgent = async () => {
    setCreating(true)
    try {
      const created = await api.createAgent({ name: 'Neuer Agent' })
      notify.success('Agent angelegt — jetzt Persona und Systemprompt zuweisen.')
      navigate(wsPath(`/agents/${created.id}`))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
      setCreating(false)
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Agents"
          description="Konfigurierte Agents — Persona × Template, einmal klicken zum Kopieren."
          actions={
            <Button
              type="button"
              variant="brand"
              disabled={isViewer || creating}
              onClick={() => void createAgent()}
              title={isViewer ? 'Viewer können keine Agents anlegen' : undefined}
              data-testid="new-agent"
            >
              <Plus className="h-4 w-4" />
              Neuen Agent erstellen
            </Button>
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
                <Button
                  type="button"
                  variant="brand"
                  disabled={isViewer || creating}
                  onClick={() => void createAgent()}
                  title={isViewer ? 'Viewer können keine Agents anlegen' : undefined}
                  data-testid="new-agent-empty"
                >
                  <Plus className="h-4 w-4" />
                  Neuen Agent erstellen
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
                {agent.activatable ? null : <Badge variant="outline">Unvollständig</Badge>}
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
