import { Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook, PlaybookRef } from '@/api/types'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Section } from '@/components/layout/Section'
import { Stack } from '@/components/layout/Stack'
import { CONTENT_LOCALE_OPTIONS } from '@/components/forms/content-languages'
import { DataView } from '@/components/data/DataView'
import { Button } from '@/components/ui/button'
import { useAgents } from '@/hooks/useAgents'
import {
  useAgentFilterParam,
  useListFilters,
  useLocaleFilterParam,
  type ListFilterAccessors,
} from '@/hooks/useListFilters'
import { usePlaybooks } from '@/hooks/usePlaybooks'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { groupPlaybooks, parseGroupMode } from '../lib/grouping'
import { splitTriggers } from '@/lib/triggers'

import { PlaybookListToolbar } from '../components/PlaybookListToolbar'
import { PlaybookRow } from '../components/PlaybookRow'
import {
  PlaybooksNoResults,
  PlaybooksOnboarding,
} from '../components/PlaybooksEmptyStates'

export function PlaybooksPage() {
  const { t } = useTranslation(['playbooks', 'data', 'common'])
  // Serverseitige Agent-/Sprach-Facette (WP-B, ADR-0045): Params VOR dem
  // Daten-Hook lesen, damit ein Facetten-Wechsel den Refetch ausloest.
  const agentFilter = useAgentFilterParam()
  const localeFilter = useLocaleFilterParam()
  const { playbooks, loading, error } = usePlaybooks(
    agentFilter || undefined,
    localeFilter || undefined,
  )
  const { agents } = useAgents()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<Playbook>>(
    () => ({
      name: (playbook) => playbook.name,
      status: (playbook) => playbook.current_status,
      hasPendingDraft: (playbook) => playbook.has_pending_draft,
      tags: (playbook) => playbook.tags,
      type: (playbook) => playbook.type,
      // Suche trifft „Name oder Trigger" (Design-Handoff §Filterleiste).
      searchText: (playbook) => splitTriggers(playbook.triggers),
    }),
    [],
  )
  const filters = useListFilters(playbooks, accessors)

  // Rueckrichtung der Composite-Beziehung, clientseitig aus den geladenen
  // compose_children abgeleitet: Kind-ID → Eltern-Referenz (erste gewinnt).
  // Plus Lookup Kind-ID → Voll-Objekt fuer Status/Version in Kind-Zeilen.
  const { parentByChildId, playbookById } = useMemo(() => {
    const parents = new Map<string, PlaybookRef>()
    const byId = new Map<string, Playbook>()
    for (const playbook of playbooks) {
      byId.set(playbook.id, playbook)
      for (const child of playbook.compose_children ?? []) {
        if (!parents.has(child.id)) {
          parents.set(child.id, { id: playbook.id, name: playbook.name })
        }
      }
    }
    return { parentByChildId: parents, playbookById: byId }
  }, [playbooks])

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
    if (groupMode === 'tag') {
      return key === '' ? t('playbooks:list.groups.untagged') : key
    }
    return key === '' ? t('playbooks:list.groups.untyped') : key
  }

  const renderRow = (playbook: Playbook) => (
    <PlaybookRow
      key={playbook.id}
      playbook={playbook}
      wsPath={wsPath}
      parent={parentByChildId.get(playbook.id)}
      resolveChild={(ref) => playbookById.get(ref.id)}
    />
  )

  // Onboarding nur, wenn der Workspace wirklich leer ist — bei aktiver
  // Agent-/Sprach-Facette kommt die Liste serverseitig gefiltert an, dann
  // ist „leer" ein Filter-Ergebnis.
  const isOnboarding = playbooks.length === 0 && filters.agent === '' && filters.locale === ''
  const showToolbar = playbooks.length > 0 || filters.agent !== '' || filters.locale !== ''

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('playbooks:list.title')}
          titleAddon={
            playbooks.length > 0 ? (
              <span
                className="rounded-full bg-muted px-2 py-0.5 text-sm font-medium text-muted-foreground tabular-nums"
                aria-label={t('playbooks:list.countLabel', { count: playbooks.length })}
              >
                {playbooks.length}
              </span>
            ) : undefined
          }
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
        {showToolbar ? (
          <PlaybookListToolbar
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            active={filters.active}
            onReset={filters.reset}
            availableTags={filters.availableTags}
            tag={filters.tag}
            onTagChange={filters.setTag}
            availableTypes={filters.availableTypes}
            type={filters.type}
            onTypeChange={filters.setType}
            agents={agents}
            agent={filters.agent}
            onAgentChange={filters.setAgent}
            locales={CONTENT_LOCALE_OPTIONS}
            locale={filters.locale}
            onLocaleChange={filters.setLocale}
            groupOptions={[
              { value: '', label: t('playbooks:list.group.none') },
              { value: 'type', label: t('playbooks:list.group.type') },
              { value: 'composite', label: t('playbooks:list.group.composite') },
              { value: 'tag', label: t('playbooks:list.group.tag') },
            ]}
            group={filters.group}
            onGroupChange={filters.setGroup}
          />
        ) : null}

        <DataView loading={loading && playbooks.length === 0} error={error}>
          {isOnboarding ? (
            <PlaybooksOnboarding newHref={wsPath('/playbooks/new')} />
          ) : filters.filtered.length === 0 ? (
            <PlaybooksNoResults query={filters.query} onReset={filters.reset} />
          ) : groupMode === 'none' ? (
            <div className="flex flex-col gap-3">{filters.filtered.map(renderRow)}</div>
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
                  <div className="flex flex-col gap-3">{group.items.map(renderRow)}</div>
                </Section>
              ))}
            </Stack>
          )}
        </DataView>
      </Stack>
    </Container>
  )
}
