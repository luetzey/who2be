import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { SaveIndicator } from '@/components/data/BranchStatus'
import { cn } from '@/lib/utils'
import type { AutoSaveState } from '@/hooks/useAutoSaveDraft'

// Design-Handoff „Playbooks-Redesign" §Review-Banner: ersetzt den
// BranchStatus-Block auf der Playbook-Detail-Seite. Links die
// Branch-Zusammenfassung („Aktiv: v2 → v3 wartet auf Review", Dots aus den
// --status-*-Tokens), rechts Save-Indikator + Aktionen.
//
// Bleibt reines Layout (Branch-Graph-Anzeige, Issue #391): die Aktionen
// selbst kommen als fertiger Slot von aussen (die zentrale
// `StatusActionBar` — sie bringt ihre eigene `role="toolbar"`-Leiste mit,
// daher wird hier keine zweite Toolbar mehr um den Slot gelegt).

interface BannerNode {
  status: VersionStatus
  label: string
  emphasized: boolean
}

interface ReviewBannerProps {
  activeVersion?: number
  draftVersion?: number
  reviewVersion?: number
  inactiveVersion?: number
  saveState?: AutoSaveState
  actions?: ReactNode
}

export function ReviewBanner({
  activeVersion,
  draftVersion,
  reviewVersion,
  inactiveVersion,
  saveState,
  actions,
}: ReviewBannerProps) {
  const { t } = useTranslation(['playbooks', 'data'])

  const nodes: BannerNode[] = []
  if (activeVersion !== undefined) {
    nodes.push({
      status: 'active',
      label: t('playbooks:detail.banner.activeNode', { version: activeVersion }),
      emphasized: true,
    })
  }
  if (reviewVersion !== undefined) {
    nodes.push({
      status: 'review',
      label: t('playbooks:detail.banner.reviewWaiting', { version: reviewVersion }),
      emphasized: activeVersion === undefined,
    })
  }
  if (draftVersion !== undefined) {
    nodes.push({
      status: 'draft',
      label: t('playbooks:detail.banner.draftOpen', { version: draftVersion }),
      emphasized: activeVersion === undefined && reviewVersion === undefined,
    })
  }
  if (nodes.length === 0 && inactiveVersion !== undefined) {
    nodes.push({
      status: 'inactive',
      label: t('playbooks:detail.banner.inactiveCurrent', { version: inactiveVersion }),
      emphasized: true,
    })
  }

  if (nodes.length === 0 && actions === undefined) {
    return null
  }

  return (
    <section
      className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-brand/25 bg-brand/5 p-4"
      aria-label={t('data:branch.label')}
      data-testid="review-banner"
    >
      <div className="flex flex-wrap items-center gap-3" data-testid="branch-graph">
        {nodes.map((node, index) => (
          <span key={node.status} className="flex items-center gap-3">
            {index > 0 ? (
              <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
            ) : null}
            <span
              className={cn(
                'inline-flex items-center gap-2 text-sm font-medium',
                node.emphasized ? 'text-foreground' : 'text-muted-foreground',
              )}
              data-testid={`branch-node-${node.status}`}
            >
              <span
                className="inline-block size-2 rounded-full"
                style={{ backgroundColor: `var(--status-${node.status})` }}
                aria-hidden="true"
              />
              {node.label}
            </span>
          </span>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {saveState !== undefined ? <SaveIndicator state={saveState} /> : null}
        {actions}
      </div>
    </section>
  )
}
