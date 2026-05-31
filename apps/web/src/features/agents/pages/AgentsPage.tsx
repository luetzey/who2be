import { Bot, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { useAgents } from '../hooks/useAgents'

export function AgentsPage() {
  const { agents, loading, error } = useAgents()
  const wsPath = useWorkspacePath()
  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Agents"
          description="Konfigurierte Agents — Persona × Template, einmal klicken zum Kopieren."
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/agents/new')}>
                <Plus className="h-4 w-4" />
                Neuer Agent
              </Link>
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
              <Badge variant={agent.status === 'enabled' ? 'default' : 'outline'}>
                {agent.status === 'enabled' ? 'Aktiv' : 'Deaktiviert'}
              </Badge>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
