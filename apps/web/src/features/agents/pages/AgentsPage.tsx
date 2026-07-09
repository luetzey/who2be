import { Bot, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
import { useAgents } from '@/hooks/useAgents'
import { notify } from '@/lib/feedback'

export function AgentsPage() {
  const { t } = useTranslation('agents')
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
      notify.success(t('toast.created'))
      navigate(wsPath(`/agents/${created.id}`))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('toast.createError'))
      setCreating(false)
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('page.title')}
          description={t('page.description')}
          actions={
            <Button
              type="button"
              variant="brand"
              disabled={isViewer || creating}
              onClick={() => void createAgent()}
              title={isViewer ? t('page.viewerNoCreate') : undefined}
              data-testid="new-agent"
            >
              <Plus className="h-4 w-4" />
              {t('page.newAgent')}
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
              title={t('page.empty.title')}
              description={t('page.empty.description')}
              action={
                <Button
                  type="button"
                  variant="brand"
                  disabled={isViewer || creating}
                  onClick={() => void createAgent()}
                  title={isViewer ? t('page.viewerNoCreate') : undefined}
                  data-testid="new-agent-empty"
                >
                  <Plus className="h-4 w-4" />
                  {t('page.newAgent')}
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
                {agent.activatable ? null : (
                  <Badge variant="outline">{t('status.incomplete')}</Badge>
                )}
                <Badge variant={agent.status === 'enabled' ? 'default' : 'outline'}>
                  {agent.status === 'enabled' ? t('status.enabled') : t('status.disabled')}
                </Badge>
              </div>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
