import {
  AlertTriangle,
  Bot,
  Brain,
  FileText,
  GitBranch,
  Plus,
  Search,
  SlidersHorizontal,
  Users,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
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
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { useAgents } from '@/hooks/useAgents'
import { notify } from '@/lib/feedback'

import { CopyPromptButton } from '../components/CopyPromptButton'

// Agent-Status-Modell (enabled/disabled + activatable) auf disjunkte Listen-
// Kategorien mappen. Unvollstaendig hat Vorrang, damit sich Filter-Zaehler nicht
// ueberschneiden (wie im Design-Handoff). Farbe kommt aus den `--status-*`-Tokens.
type AgentFilter = 'all' | 'active' | 'disabled' | 'incomplete'

function agentCategory(agent: Agent): Exclude<AgentFilter, 'all'> {
  if (!agent.activatable) return 'incomplete'
  return agent.status === 'enabled' ? 'active' : 'disabled'
}

const CATEGORY_TOKEN: Record<Exclude<AgentFilter, 'all'>, string> = {
  active: 'active',
  disabled: 'inactive',
  incomplete: 'draft',
}

function AgentStatusPill({ agent }: { agent: Agent }) {
  const { t } = useTranslation('agents')
  const category = agentCategory(agent)
  const label =
    category === 'incomplete'
      ? t('status.incomplete')
      : category === 'active'
        ? t('status.enabled')
        : t('status.disabled')

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span
        className="inline-block size-2 rounded-full"
        style={{ backgroundColor: `var(--status-${CATEGORY_TOKEN[category]})` }}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

// Segmentierter Status-Chip — gleiche Optik wie ListFilterBar (rounded-full,
// Status-Punkt + Zaehler), aber auf das Agent-Status-Modell zugeschnitten.
function FilterChip({
  label,
  count,
  token,
  selected,
  onClick,
}: {
  label: string
  count: number
  token?: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={selected ? 'default' : 'outline'}
      aria-pressed={selected}
      onClick={onClick}
      className="h-8 gap-1.5 rounded-full"
    >
      {token ? (
        <span
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: `var(--status-${token})` }}
          aria-hidden="true"
        />
      ) : null}
      <span>{label}</span>
      <span className={cn('tabular-nums', selected ? 'opacity-90' : 'text-muted-foreground')}>
        {count}
      </span>
    </Button>
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
  const [status, setStatus] = useState<AgentFilter>('all')
  const [query, setQuery] = useState('')

  const counts = useMemo(() => {
    const acc = { all: agents.length, active: 0, disabled: 0, incomplete: 0 }
    for (const agent of agents) acc[agentCategory(agent)] += 1
    return acc
  }, [agents])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return agents.filter((agent) => {
      if (status !== 'all' && agentCategory(agent) !== status) return false
      if (needle !== '' && !agent.name.toLowerCase().includes(needle)) return false
      return true
    })
  }, [agents, status, query])

  const filterActive = status !== 'all' || query.trim() !== ''

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

  const chips: { key: AgentFilter; label: string; count: number; token?: string }[] = [
    { key: 'all', label: t('filter.all'), count: counts.all },
    { key: 'active', label: t('status.enabled'), count: counts.active, token: 'active' },
    { key: 'disabled', label: t('status.disabled'), count: counts.disabled, token: 'inactive' },
    { key: 'incomplete', label: t('status.incomplete'), count: counts.incomplete, token: 'draft' },
  ]

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
            <>
              <Card>
                <CardContent className="flex flex-col gap-4 pt-6">
                  <div
                    className="flex flex-wrap items-center gap-2"
                    role="group"
                    aria-label={t('filter.statusGroup')}
                  >
                    {chips.map((chip) => (
                      <FilterChip
                        key={chip.key}
                        label={chip.label}
                        count={chip.count}
                        token={chip.token}
                        selected={status === chip.key}
                        onClick={() => setStatus(chip.key)}
                      />
                    ))}
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="agents-search">{t('filter.searchLabel')}</Label>
                    <div className="relative">
                      <Search
                        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                        aria-hidden="true"
                      />
                      {/* pl-9 ist bewusst off-scale (funktionaler Icon-Inset):
                          left-3 (12px) + size-4 (16px) + 8px Luft = 36px, damit der
                          Eingabetext nicht unter dem Such-Icon liegt. */}
                      <Input
                        id="agents-search"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder={t('filter.searchPlaceholder')}
                        className="pl-9"
                      />
                    </div>
                  </div>
                  {filterActive ? (
                    <div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-8 gap-1 px-2 text-xs"
                        onClick={() => {
                          setStatus('all')
                          setQuery('')
                        }}
                      >
                        <X className="size-4" aria-hidden="true" />
                        {t('filter.reset')}
                      </Button>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              {filtered.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title={t('filter.emptyTitle')}
                  description={t('filter.emptyDescription')}
                />
              ) : (
                <div className="flex flex-col gap-3">
                  {filtered.map((agent) => {
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
                          <>
                            {missesPersona ? (
                              <MetaPill icon={AlertTriangle} tone="destructive">
                                {t('card.personaMissing')}
                              </MetaPill>
                            ) : agent.persona_name ? (
                              <MetaPill icon={Users} iconTone="persona">
                                {agent.persona_name}
                              </MetaPill>
                            ) : null}
                            {missesTemplate ? (
                              <MetaPill icon={AlertTriangle} tone="destructive">
                                {t('card.templateMissing')}
                              </MetaPill>
                            ) : agent.template_name ? (
                              <MetaPill icon={FileText} iconTone="date">
                                {agent.template_version != null
                                  ? t('card.templateWithVersion', {
                                      name: agent.template_name,
                                      version: agent.template_version,
                                    })
                                  : agent.template_name}
                              </MetaPill>
                            ) : null}
                            <MetaPill icon={GitBranch} iconTone="playbook">
                              {t('card.playbookCount', { count: agent.playbook_count ?? 0 })}
                            </MetaPill>
                            {(agent.pending_memory_count ?? 0) > 0 ? (
                              // Aufmerksamkeits-Pill (ADR-0044): liegt via z-10
                              // ueber dem Stretched-Link der Karte und springt
                              // direkt in die Gedaechtnis-Sektion des Agenten.
                              <Link
                                to={wsPath(`/agents/${agent.id}#memory`)}
                                className="relative z-10 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                                aria-label={t('card.pendingMemoriesAria', {
                                  count: agent.pending_memory_count,
                                  name: agent.name,
                                })}
                                data-testid="pending-memories-pill"
                              >
                                <MetaPill
                                  icon={Brain}
                                  tone="brand"
                                  className="transition-colors duration-[var(--duration-fast)] hover:bg-brand/20"
                                >
                                  {t('card.pendingMemories', {
                                    count: agent.pending_memory_count,
                                  })}
                                </MetaPill>
                              </Link>
                            ) : null}
                          </>
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
            </>
          )}
        </DataView>
      </Stack>
    </Container>
  )
}
