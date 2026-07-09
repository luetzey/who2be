import { BookOpen, Plus } from 'lucide-react'
import { Fragment, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook } from '@/api/types'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Section } from '@/components/layout/Section'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAgents } from '@/hooks/useAgents'
import {
  useAgentFilterParam,
  useListFilters,
  type ListFilterAccessors,
} from '@/hooks/useListFilters'
import { usePlaybooks } from '@/hooks/usePlaybooks'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { groupPlaybooks, parseGroupMode } from '../lib/grouping'
import { splitTriggers } from '@/lib/triggers'

// WP-D2: maximal sichtbare Trigger-Pills pro Zeile — der Rest wird zu „+N",
// damit triggerreiche Playbooks die Listenzeile nicht ueberladen.
const MAX_VISIBLE_TRIGGERS = 3

export function PlaybooksPage() {
  const { t } = useTranslation(['playbooks', 'data', 'common'])
  // Serverseitige Agent-Facette (WP-B): Param VOR dem Daten-Hook lesen,
  // damit ein Facetten-Wechsel den Refetch ausloest.
  const agentFilter = useAgentFilterParam()
  const { playbooks, loading, error } = usePlaybooks(agentFilter || undefined)
  const { agents } = useAgents()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<Playbook>>(
    () => ({
      name: (playbook) => playbook.name,
      status: (playbook) => playbook.current_status,
      hasPendingDraft: (playbook) => playbook.has_pending_draft,
      tags: (playbook) => playbook.tags,
      type: (playbook) => playbook.type,
    }),
    [],
  )
  const filters = useListFilters(playbooks, accessors)

  // WP-D3: Gruppierung ist eine Anzeige-Praeferenz auf der bereits
  // gefilterten Liste — unbekannte `?group=`-Werte fallen auf `none` zurueck.
  const groupMode = parseGroupMode(filters.group)
  const groups = useMemo(
    () => groupPlaybooks(filters.filtered, groupMode),
    [filters.filtered, groupMode],
  )
  const groupLabel = (key: string): string => {
    if (groupMode === 'composite') {
      return key === 'composite'
        ? t('playbooks:list.groups.composite')
        : t('playbooks:list.groups.standalone')
    }
    return key === '' ? t('playbooks:list.groups.untyped') : key
  }

  const renderPlaybook = (playbook: Playbook) => {
    const triggers = splitTriggers(playbook.triggers)
    const visibleTriggers = triggers.slice(0, MAX_VISIBLE_TRIGGERS)
    const hiddenTriggerCount = triggers.length - visibleTriggers.length
    const composeChildren = playbook.compose_children ?? []
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={wsPath(`/playbooks/${playbook.id}`)}
              className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
            >
              {playbook.name}
            </Link>
            <StatusBadge
              status={playbook.current_status}
              pendingDraft={playbook.has_pending_draft}
            />
            {playbook.is_composite === true ? (
              <Badge variant="secondary">Composite</Badge>
            ) : null}
            <span className="text-xs text-muted-foreground">
              {playbook.type} · v{playbook.current_version}
            </span>
          </div>
          {visibleTriggers.length > 0 || composeChildren.length > 0 ? (
            <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground">
              {visibleTriggers.map((trigger) => (
                <Badge key={trigger} variant="outline">
                  {trigger}
                </Badge>
              ))}
              {hiddenTriggerCount > 0 ? (
                <Badge
                  variant="outline"
                  aria-label={t('playbooks:list.moreTriggers', { count: hiddenTriggerCount })}
                >
                  +{hiddenTriggerCount}
                </Badge>
              ) : null}
              {composeChildren.length > 0 ? (
                <span className="min-w-0">
                  {t('playbooks:list.composedOf')}{' '}
                  {composeChildren.map((child, index) => (
                    <Fragment key={child.id}>
                      {index > 0 ? <span aria-hidden="true"> · </span> : null}
                      <Link
                        to={wsPath(`/playbooks/${child.id}`)}
                        className="rounded-sm text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      >
                        {child.name}
                      </Link>
                    </Fragment>
                  ))}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        {playbook.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1" aria-label={t('common:fields.tags')}>
            {playbook.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  const emptyState =
    // Bei aktiver Agent-Facette kommt die Liste serverseitig gefiltert
    // an — dann ist "leer" ein Filter-Ergebnis, kein leerer Workspace.
    playbooks.length === 0 && filters.agent === '' ? (
      <EmptyState
        icon={BookOpen}
        title={t('playbooks:list.empty.title')}
        description={t('playbooks:list.empty.description')}
        action={
          <Button asChild variant="brand">
            <Link to={wsPath('/playbooks/new')}>
              <Plus className="h-4 w-4" />
              {t('playbooks:list.newButton')}
            </Link>
          </Button>
        }
      />
    ) : (
      <EmptyState
        icon={BookOpen}
        title={t('data:filter.emptyFilteredTitle')}
        description={t('data:filter.emptyFilteredDescription')}
        action={
          <Button type="button" variant="outline" onClick={filters.reset}>
            {t('data:filter.reset')}
          </Button>
        }
      />
    )

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('playbooks:list.title')}
          description={t('playbooks:list.description')}
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/playbooks/new')}>
                <Plus className="h-4 w-4" />
                {t('playbooks:list.newButton')}
              </Link>
            </Button>
          }
        />
        {playbooks.length > 0 || filters.agent !== '' ? (
          <ListFilterBar
            idPrefix="playbooks"
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            availableTags={filters.availableTags}
            tag={filters.tag}
            onTagChange={filters.setTag}
            availableTypes={filters.availableTypes}
            type={filters.type}
            onTypeChange={filters.setType}
            agents={agents}
            agent={filters.agent}
            onAgentChange={filters.setAgent}
            groupOptions={[
              { value: '', label: t('playbooks:list.group.none') },
              { value: 'type', label: t('playbooks:list.group.type') },
              { value: 'composite', label: t('playbooks:list.group.composite') },
            ]}
            group={filters.group}
            onGroupChange={filters.setGroup}
            active={filters.active}
            onReset={filters.reset}
          />
        ) : null}

        {groupMode === 'none' || filters.filtered.length === 0 ? (
          <DataList
            items={filters.filtered}
            loading={loading}
            error={error}
            getKey={(playbook) => playbook.id}
            empty={emptyState}
            renderItem={renderPlaybook}
          />
        ) : (
          // WP-D3: Sektionen pro Gruppe mit Header + Zaehler; leere Gruppen
          // liefert `groupPlaybooks` gar nicht erst.
          <Stack gap="lg">
            {groups.map((group) => (
              <Section key={group.key} ariaLabel={groupLabel(group.key)} className="gap-2">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                  {groupLabel(group.key)}
                  <span className="font-normal tabular-nums">({group.items.length})</span>
                </h2>
                <DataList
                  items={group.items}
                  getKey={(playbook) => playbook.id}
                  renderItem={renderPlaybook}
                />
              </Section>
            ))}
          </Stack>
        )}
      </Stack>
    </Container>
  )
}
