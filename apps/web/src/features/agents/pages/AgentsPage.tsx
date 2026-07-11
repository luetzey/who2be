import { AlertTriangle, Bot, Plus, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { useAgents } from '@/hooks/useAgents'
import { notify } from '@/lib/feedback'

import { CopyPromptButton } from '../components/CopyPromptButton'

// Agent-Status-Modell (enabled/disabled + activatable) auf ein einzelnes
// Listen-Label mappen. Unvollstaendig hat Vorrang vor enabled/disabled, damit
// die Kategorien disjunkt sind (wie die Filter-Zaehler im Design-Handoff).
// Farbe kommt aus den `--status-*`-Tokens (Muster: StatusBadge/ListFilterBar),
// nie als alleiniges Signal — Punkt + Text-Label zusammen (design-language §11).
function AgentStatusPill({ agent }: { agent: Agent }) {
  const { t } = useTranslation('agents')
  const { token, label } = !agent.activatable
    ? { token: 'draft', label: t('status.incomplete') }
    : agent.status === 'enabled'
      ? { token: 'active', label: t('status.enabled') }
      : { token: 'inactive', label: t('status.disabled') }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span
        className="inline-block size-2 rounded-full"
        style={{ backgroundColor: `var(--status-${token})` }}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

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

  const newAgentCta = (
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
  )

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('page.title')}
          titleAddon={
            agents.length > 0 ? (
              <span
                className="rounded-full bg-muted px-2 py-0.5 text-sm font-medium text-muted-foreground tabular-nums"
                aria-label={t('card.countAria', { count: agents.length })}
              >
                {agents.length}
              </span>
            ) : undefined
          }
          description={t('page.description')}
          actions={newAgentCta}
        />
        <DataView loading={loading && agents.length === 0} error={error}>
          {agents.length === 0 ? (
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
          ) : (
            <div className="flex flex-col gap-3">
              {agents.map((agent) => {
                const missesPersona = agent.missing.includes('persona')
                const missesTemplate = agent.missing.includes('template')
                return (
                  <EntityCard
                    key={agent.id}
                    icon={Bot}
                    iconTone="catalog"
                    title={agent.name}
                    href={wsPath(`/agents/${agent.id}`)}
                    status={<AgentStatusPill agent={agent} />}
                    description={agent.description || undefined}
                    meta={
                      missesPersona || missesTemplate ? (
                        <>
                          {missesPersona ? (
                            <MetaPill icon={AlertTriangle} tone="destructive">
                              {t('card.personaMissing')}
                            </MetaPill>
                          ) : null}
                          {missesTemplate ? (
                            <MetaPill icon={AlertTriangle} tone="destructive">
                              {t('card.templateMissing')}
                            </MetaPill>
                          ) : null}
                        </>
                      ) : undefined
                    }
                    actions={
                      agent.activatable ? (
                        <CopyPromptButton
                          agentId={agent.id}
                          disabled={agent.status !== 'enabled'}
                        />
                      ) : (
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath(`/agents/${agent.id}`)}>
                            <SlidersHorizontal className="h-4 w-4" />
                            {t('card.setup')}
                          </Link>
                        </Button>
                      )
                    }
                  />
                )
              })}
            </div>
          )}
        </DataView>
      </Stack>
    </Container>
  )
}
