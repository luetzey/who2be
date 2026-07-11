import { ChevronRight, Layers, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook, PlaybookRef, VersionStatus } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { splitTriggers } from '@/lib/triggers'

import { PlaybookTypeIcon } from './PlaybookTypeIcon'

// Design-Handoff „Playbooks-Redesign" §Row: eine Karte pro Playbook mit
// Typ-Icon, sanftem Status (Dot statt Badge), sichtbaren Triggern,
// aufklappbarem Composite-Footer und „Teil von"-Marker. Die ganze Karte ist
// per Stretched-Link klickbar (Name-Link mit after-Overlay); innenliegende
// Links/Buttons liegen via `relative` darueber.

// Maximal sichtbare Trigger-Chips pro Zeile — der Rest wird zu „+N".
const MAX_VISIBLE_TRIGGERS = 3

interface PlaybookRowProps {
  playbook: Playbook
  /** Workspace-Pfad-Builder der Page (useWorkspacePath). */
  wsPath: (path: string) => string
  /** Eltern-Composite (Rueckrichtung aus compose_children der Liste). */
  parent?: PlaybookRef
  /** Voll-Objekt eines Sub-Playbooks fuer Status/Version in der Kind-Zeile. */
  resolveChild?: (ref: PlaybookRef) => Playbook | undefined
}

function StatusDotLabel({
  status,
  version,
  dotClassName,
}: {
  status: VersionStatus | undefined
  version: number
  dotClassName?: string
}) {
  const { t } = useTranslation('common')
  if (status === undefined) return null
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span
        className={cn('inline-block size-2 rounded-full', dotClassName)}
        style={{ backgroundColor: `var(--status-${status})` }}
        aria-hidden="true"
      />
      {t(`status.${status}`)} · v{version}
    </span>
  )
}

export function PlaybookRow({ playbook, wsPath, parent, resolveChild }: PlaybookRowProps) {
  const { t } = useTranslation(['playbooks', 'data', 'common'])
  const [expanded, setExpanded] = useState(false)

  const triggers = splitTriggers(playbook.triggers)
  const visibleTriggers = triggers.slice(0, MAX_VISIBLE_TRIGGERS)
  const hiddenTriggerCount = triggers.length - visibleTriggers.length
  const composeChildren = playbook.compose_children ?? []

  return (
    <article
      className="relative flex gap-4 rounded-xl border bg-card p-4 shadow-card transition-[box-shadow,border-color] duration-[var(--duration-fast)] ease-spring hover:shadow-popover"
      data-testid="playbook-row"
    >
      <PlaybookTypeIcon type={playbook.type} />

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={wsPath(`/playbooks/${playbook.id}`)}
            className="rounded-sm text-sm font-semibold text-foreground after:absolute after:inset-0 after:rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {playbook.name}
          </Link>
          <StatusDotLabel status={playbook.current_status} version={playbook.current_version} />
          {playbook.has_pending_draft === true ? (
            <span className="rounded-full bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
              {t('data:filter.pendingDraft')}
            </span>
          ) : null}
        </div>

        {playbook.content.description !== '' ? (
          <p className="text-sm text-muted-foreground">{playbook.content.description}</p>
        ) : null}

        {parent !== undefined ? (
          <Link
            to={wsPath(`/playbooks/${parent.id}`)}
            className="relative mt-1 inline-flex w-fit items-center gap-1.5 rounded-md bg-pill-catalog px-2 py-0.5 text-xs font-medium text-pill-catalog-fg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <Layers className="size-3" aria-hidden="true" />
            {t('playbooks:list.partOf', { name: parent.name })}
          </Link>
        ) : null}

        {visibleTriggers.length > 0 ? (
          <div
            className="mt-1 flex flex-wrap items-center gap-2"
            role="list"
            aria-label={t('playbooks:detail.triggerList')}
          >
            <Zap className="size-3.5 text-muted-foreground" aria-hidden="true" />
            {visibleTriggers.map((trigger) => (
              <span
                key={trigger}
                role="listitem"
                className="rounded-md bg-muted px-2 py-0.5 text-xs text-foreground"
              >
                {trigger}
              </span>
            ))}
            {hiddenTriggerCount > 0 ? (
              <span
                className="text-xs text-muted-foreground"
                aria-label={t('playbooks:list.moreTriggers', { count: hiddenTriggerCount })}
              >
                +{hiddenTriggerCount}
              </span>
            ) : null}
          </div>
        ) : null}

        {composeChildren.length > 0 ? (
          <div className="relative mt-2 overflow-hidden rounded-lg bg-pill-catalog/45">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-expanded={expanded}
              onClick={() => setExpanded((open) => !open)}
              className="h-auto w-full justify-start gap-2 px-3 py-2 text-xs font-normal text-pill-catalog-fg hover:bg-pill-catalog/60 hover:text-pill-catalog-fg"
            >
              <Layers className="size-3.5" aria-hidden="true" />
              <span className="font-semibold">
                {t('playbooks:list.subPlaybooksCount', { count: composeChildren.length })}
              </span>
              <span className="min-w-0 truncate opacity-80">
                {composeChildren.map((child) => child.name).join(' · ')}
              </span>
              <ChevronRight
                className={cn(
                  'ml-auto size-3.5 transition-transform duration-[var(--duration-fast)] ease-standard',
                  expanded && 'rotate-90',
                )}
                aria-hidden="true"
              />
            </Button>
            {expanded ? (
              <ol
                className="flex flex-col gap-1.5 px-2 pb-2"
                aria-label={t('playbooks:list.subPlaybooksListLabel')}
              >
                {composeChildren.map((child, index) => {
                  const detail = resolveChild?.(child)
                  return (
                    <li key={child.id}>
                      <Link
                        to={wsPath(`/playbooks/${child.id}`)}
                        className="flex items-center gap-2 rounded-lg border border-pill-catalog-fg/20 bg-card px-3 py-2 text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      >
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-pill-catalog text-xs font-bold text-pill-catalog-fg">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm font-medium">
                          {child.name}
                        </span>
                        {detail !== undefined ? (
                          <StatusDotLabel
                            status={detail.current_status}
                            version={detail.current_version}
                          />
                        ) : null}
                        <ChevronRight
                          className="size-4 text-muted-foreground/60"
                          aria-hidden="true"
                        />
                      </Link>
                    </li>
                  )
                })}
              </ol>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-col items-end justify-between gap-2">
        {playbook.tags.length > 0 ? (
          <div className="flex flex-wrap justify-end gap-1" aria-label={t('common:fields.tags')}>
            {playbook.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        ) : null}
        <ChevronRight className="size-4 text-muted-foreground/60" aria-hidden="true" />
      </div>
    </article>
  )
}
