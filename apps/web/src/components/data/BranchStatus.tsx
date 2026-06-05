import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import type { AutoSaveState } from '@/hooks/useAutoSaveDraft'

// Git-Style Branch-Visualisierung + Action-Bar (Phase 3-Runde-3 Track 2).
//
// Lebt unter `components/data/`, weil sie zwar ueber drei Features (Persona,
// Playbook, Resource) geteilt wird, aber semantisch Datendarstellung ist —
// kein reines Layout-Primitive. Der Auto-Save-Indikator ist via
// `aria-live="polite"` als Live-Region ausgezeichnet (Design-Language §11).

export type BranchActionVariant = 'brand' | 'default' | 'outline' | 'destructive'

export interface BranchAction {
  key: string
  label: string
  onClick: () => void
  variant: BranchActionVariant
  disabled?: boolean
  title?: string
}

export interface BranchStatusProps {
  activeVersion?: number
  draftVersion?: number
  reviewVersion?: number
  inactiveVersion?: number
  currentVersion: number
  saveState?: AutoSaveState
  actions: BranchAction[]
  // Optional: kompakter Modus fuer Card-Header.
  className?: string
}

function nodeFor(label: string, displayLabel: string, version: number, accent: boolean) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs',
        accent
          ? 'border-brand/40 bg-brand/10 text-brand'
          : 'border-border bg-muted text-muted-foreground',
      )}
      data-testid={`branch-node-${label}`}
    >
      <span aria-hidden="true">{accent ? '●' : '○'}</span>
      <span>
        v{version} {displayLabel}
      </span>
    </span>
  )
}

function describeSaveState(state: AutoSaveState, now: Date, t: TFunction): string {
  switch (state.status) {
    case 'idle':
      return t('branch.ready')
    case 'saving':
      return t('branch.saving')
    case 'saved': {
      if (state.lastSavedAt === null) {
        return t('branch.saved')
      }
      const seconds = Math.max(0, Math.floor((now.getTime() - state.lastSavedAt.getTime()) / 1000))
      if (seconds < 5) {
        return t('branch.saved')
      }
      if (seconds < 60) {
        return t('branch.savedAgoSeconds', { seconds })
      }
      const minutes = Math.floor(seconds / 60)
      return t('branch.savedAgoMinutes', { minutes })
    }
    case 'error':
      return state.errorMessage !== null
        ? t('branch.errorWithMessage', { message: state.errorMessage })
        : t('branch.error')
  }
}

function SaveIndicator({ state }: { state: AutoSaveState }) {
  const { t } = useTranslation('data')
  // 1-Sekunden-Tick fuer den "vor X s"-Text — laeuft nur in "saved", damit
  // wir nicht im Idle/Error sinnlos re-rendern.
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    if (state.status !== 'saved' || state.lastSavedAt === null) {
      return
    }
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [state.status, state.lastSavedAt])

  const tone =
    state.status === 'error'
      ? 'text-destructive'
      : state.status === 'saving'
        ? 'text-muted-foreground'
        : 'text-muted-foreground'
  return (
    <p
      className={cn('text-xs', tone)}
      role="status"
      aria-live="polite"
      data-testid="branch-save-indicator"
    >
      {describeSaveState(state, now, t)}
    </p>
  )
}

export function BranchStatus({
  activeVersion,
  draftVersion,
  reviewVersion,
  inactiveVersion,
  currentVersion,
  saveState,
  actions,
  className,
}: BranchStatusProps) {
  const { t } = useTranslation('data')
  const nodes: { label: string; version: number; accent: boolean }[] = []
  if (activeVersion !== undefined) {
    nodes.push({ label: 'active', version: activeVersion, accent: currentVersion === activeVersion })
  }
  if (reviewVersion !== undefined) {
    nodes.push({ label: 'review', version: reviewVersion, accent: currentVersion === reviewVersion })
  }
  if (draftVersion !== undefined) {
    nodes.push({ label: 'draft', version: draftVersion, accent: currentVersion === draftVersion })
  }
  if (
    nodes.length === 0 &&
    inactiveVersion !== undefined
  ) {
    nodes.push({ label: 'inactive', version: inactiveVersion, accent: true })
  }

  return (
    <section
      className={cn('flex flex-col gap-3', className)}
      aria-label={t('branch.label')}
    >
      <div className="flex flex-wrap items-center gap-2" data-testid="branch-graph">
        {nodes.map((node, index) => (
          <span key={node.label} className="flex items-center gap-2">
            {index > 0 ? (
              <span aria-hidden="true" className="text-muted-foreground">
                ──
              </span>
            ) : null}
            {nodeFor(node.label, node.label, node.version, node.accent)}
          </span>
        ))}
        {nodes.find((n) => n.label === 'draft' && n.accent) !== undefined ? (
          <span className="text-xs text-muted-foreground">{t('branch.editing')}</span>
        ) : null}
      </div>

      {actions.length > 0 ? (
        <div
          className="flex flex-wrap items-center gap-2"
          role="toolbar"
          aria-label={t('branch.actions')}
        >
          {actions.map((action) => (
            <Button
              key={action.key}
              type="button"
              variant={action.variant}
              onClick={action.onClick}
              disabled={action.disabled}
              title={action.title}
            >
              {action.label}
            </Button>
          ))}
        </div>
      ) : null}

      {saveState !== undefined ? <SaveIndicator state={saveState} /> : null}
    </section>
  )
}
