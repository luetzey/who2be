import {
  AlertTriangle,
  Bot,
  Brain,
  FileText,
  GitBranch,
  Plus,
  Search,
  SlidersHorizontal,
  Star,
  Users,
} from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { CountPill } from '@/components/data/CountPill'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { type StatusChipOption } from '@/lib/listFilter'
import { cn } from '@/lib/utils'
import { useAgents } from '@/hooks/useAgents'
import { notify } from '@/lib/feedback'

import { CopyPromptButton } from '../components/CopyPromptButton'
import { usePendingAgentMemories } from '../hooks/usePendingAgentMemories'

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

const STATUS_VALUES: readonly AgentFilter[] = ['all', 'active', 'disabled', 'incomplete']

function isAgentFilter(value: string): value is AgentFilter {
  return (STATUS_VALUES as readonly string[]).includes(value)
}

export function AgentsPage() {
  const { t } = useTranslation('agents')
  const { agents, loading, error, reload } = useAgents()
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  // Offene Gedaechtnis-Freigaben je Agent aus `GET /memories/counts`
  // (ADR-0053 6.4.1); fuer viewer leer — kein Request, kein Pill.
  const pendingMemories = usePendingAgentMemories()
  const [creating, setCreating] = useState(false)
  // Filter-Standard §2.1 Punkt 9: Status und Suche stehen in der URL
  // (`?status=`, `?q=`), per `replace` geschrieben; der Standard „Alle“ fehlt.
  const [params, setParams] = useSearchParams()
  const rawStatus = params.get('status') ?? 'all'
  const status: AgentFilter = isAgentFilter(rawStatus) ? rawStatus : 'all'
  const query = params.get('q') ?? ''
  const setParam = useCallback(
    (key: string, value: string) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (value === '' || (key === 'status' && value === 'all')) next.delete(key)
          else next.set(key, value)
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )
  const resetFilters = useCallback(() => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('status')
        next.delete('q')
        return next
      },
      { replace: true },
    )
  }, [setParams])

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

  // Favoriten oben, alles andere darunter — innerhalb jeder Gruppe bleibt die
  // API-Reihenfolge (`created_at DESC`). Die Status-Zaehler oben bleiben
  // bewusst ungruppiert: sie zaehlen den Bestand, nicht die Ansicht.
  const groups = useMemo(() => {
    const favorites = filtered.filter((agent) => agent.is_favorite === true)
    const others = filtered.filter((agent) => agent.is_favorite !== true)
    return [
      { key: 'favorites', label: t('page.favoritesSection'), items: favorites },
      { key: 'others', label: t('page.othersSection'), items: others },
    ].filter((group) => group.items.length > 0)
  }, [filtered, t])

  // Ueberschriften erst, wenn es wirklich zwei Gruppen gibt.
  const showGroupHeadings = groups.length > 1

  // Kein Optimistic-UI (kein Muster im Repo): der Server entscheidet, danach
  // laedt `reload()` dieselbe Quelle neu, die auch die Gruppierung speist. Ein
  // fehlgeschlagener Toggle laesst die Liste unveraendert.
  const toggleFavorite = async (agent: Agent) => {
    try {
      if (agent.is_favorite === true) {
        await api.unfavoriteAgent(agent.id)
      } else {
        await api.favoriteAgent(agent.id)
      }
      reload()
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : t('card.favoriteError'))
    }
  }

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

  // Generische Status-Chips der ListFilterBar (E1). Chips mit 0 entfallen,
  // ausser „Alle“ (Standardwert) oder der gewaehlte Chip (§2.1 Punkt 1).
  const statusOptions: StatusChipOption[] = [
    { value: 'all', label: t('data:filter.all'), count: counts.all, keepWhenZero: true },
    { value: 'active', label: t('status.enabled'), count: counts.active, token: 'active' },
    { value: 'disabled', label: t('status.disabled'), count: counts.disabled, token: 'inactive' },
    {
      value: 'incomplete',
      label: t('status.incomplete'),
      count: counts.incomplete,
      token: 'draft',
    },
  ]

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('page.title')}
          titleAddon={
            agents.length > 0 ? (
              <CountPill
                count={agents.length}
                label={t('card.countAria', { count: agents.length })}
              />
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
              <ListFilterBar
                idPrefix="agents"
                statusOptions={statusOptions}
                status={status}
                onStatusChange={(value) => setParam('status', value)}
                query={query}
                onQueryChange={(value) => setParam('q', value)}
                searchPlaceholder={t('filter.searchPlaceholder')}
                active={filterActive}
                onReset={resetFilters}
              />

              {filtered.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title={t('data:filter.emptyFilteredTitle')}
                  description={t('filter.emptyDescription')}
                  action={
                    <Button type="button" variant="outline" onClick={resetFilters}>
                      {t('data:filter.reset')}
                    </Button>
                  }
                />
              ) : (
                <div className="flex flex-col gap-6">
                  {groups.map((group) => (
                    <section
                      key={group.key}
                      // Nur setzen, wenn die Ueberschrift wirklich gerendert
                      // wird — sonst zeigt das Attribut ins Leere.
                      aria-labelledby={
                        showGroupHeadings ? `agents-${group.key}-heading` : undefined
                      }
                    >
                      {/* Ueberschrift nur, wenn es zwei Gruppen gibt — eine
                          einzelne Liste braucht keinen Namen (AC 2). */}
                      {showGroupHeadings ? (
                        <h2
                          id={`agents-${group.key}-heading`}
                          className="mb-3 text-sm font-medium text-muted-foreground"
                        >
                          {group.label}
                        </h2>
                      ) : null}
                      <div className="flex flex-col gap-3">
                        {group.items.map((agent) => {
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
                                  // `min-w-0 truncate`: Persona-Namen sind
                                  // technische Bezeichner. Gemessen bei 320 px
                                  // genau 238 px — buendig an der Innenkante
                                  // ohne jede Reserve (#570 AK 2, der „kuerzt
                                  // kontrolliert" ausdruecklich zulaesst).
                                  // Woertlich das Muster aus
                                  // AgentHierarchyView.tsx:64/:98
                                  // (Vorentscheidung 1). `break-all` waere hier
                                  // falsch: sobald die Karte Zeilen-Aktionen
                                  // traegt, kollabiert die Textspalte des
                                  // EntityCard-Primitives auf 16 px, und
                                  // `break-all` zieht die Pille dann gemessen
                                  // auf 612 px Hoehe (Primitive-Fund 2).
                                  <MetaPill
                                    icon={Users}
                                    iconTone="persona"
                                    className="min-w-0 truncate"
                                  >
                                    {agent.persona_name}
                                  </MetaPill>
                                ) : null}
                                {missesTemplate ? (
                                  <MetaPill icon={AlertTriangle} tone="destructive">
                                    {t('card.templateMissing')}
                                  </MetaPill>
                                ) : agent.template_name ? (
                                  // Gemessen bei 320 px: 256 px in einer 238 px
                                  // breiten Spalte, +18 px Ueberlauf; ohne
                                  // Version sogar 319,5 px (#570 AK 2). Gleiche
                                  // Wahl und gleiche Begruendung wie an der
                                  // Persona-Pille darueber.
                                  <MetaPill
                                    icon={FileText}
                                    iconTone="date"
                                    className="min-w-0 truncate"
                                  >
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
                                {(pendingMemories[agent.id] ?? 0) > 0 ? (
                                  // Aufmerksamkeits-Pill (ADR-0044): liegt via z-10
                                  // ueber dem Stretched-Link der Karte und springt
                                  // direkt in die Gedaechtnis-Sektion des Agenten.
                                  <Link
                                    to={wsPath(`/agents/${agent.id}#memory`)}
                                    className="relative z-10 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                                    aria-label={t('card.pendingMemoriesAria', {
                                      count: pendingMemories[agent.id],
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
                                        count: pendingMemories[agent.id],
                                      })}
                                    </MetaPill>
                                  </Link>
                                ) : null}
                              </>
                            }
                            actions={
                              <>
                                {/* Liegt wie der Pending-Pill via z-10 ueber dem
                                    Stretched-Link der Karte; ohne preventDefault +
                                    stopPropagation wuerde der Klick zusaetzlich zur
                                    Detail-Seite navigieren. */}
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="relative z-10"
                                  aria-pressed={agent.is_favorite === true}
                                  aria-label={
                                    agent.is_favorite === true
                                      ? t('card.unfavorite', { name: agent.name })
                                      : t('card.favorite', { name: agent.name })
                                  }
                                  data-testid="favorite-toggle"
                                  onClick={(event) => {
                                    event.preventDefault()
                                    event.stopPropagation()
                                    void toggleFavorite(agent)
                                  }}
                                >
                                  <Star
                                    className={cn(
                                      'h-4 w-4',
                                      agent.is_favorite === true && 'fill-current text-brand',
                                    )}
                                  />
                                </Button>
                                {agent.activatable ? (
                                  <CopyPromptButton
                                    agentId={agent.id}
                                    disabled={agent.status !== 'enabled'}
                                    variant="outline"
                                  />
                                ) : (
                                  <Button asChild variant="outline" size="sm" className="min-h-10 md:min-h-0">
                                    <Link to={wsPath(`/agents/${agent.id}`)}>
                                      <SlidersHorizontal className="h-4 w-4" />
                                      {t('card.setup')}
                                    </Link>
                                  </Button>
                                )}
                              </>
                            }
                          />
                        )
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </>
          )}
        </DataView>
      </Stack>
    </Container>
  )
}
