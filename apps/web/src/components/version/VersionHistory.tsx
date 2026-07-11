import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ProvenanceEntry, VersionDiff, VersionStatus } from '@/api/types'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'

import { ProvenanceList } from './ProvenanceList'
import { VersionDiffView } from './VersionDiffView'

export interface VersionHistoryItem {
  version: number
  status?: VersionStatus
  created_at: string
}

interface VersionHistoryProps {
  versions: VersionHistoryItem[]
  /** Editor+ darf Restore auslösen (Backend-Gate: editor). */
  canEdit: boolean
  /** Stellt die Version als neue Draft wieder her (Page wired API + reload). */
  onRestore: (version: number) => Promise<void>
  /** Lädt den read-only Diff der Version gegen die aktive Version. */
  loadDiff: (version: number) => Promise<VersionDiff>
  /** Lädt die Status-Historie der Version ("warum aktiv"). */
  loadProvenance: (version: number) => Promise<ProvenanceEntry[]>
}

type PanelKind = 'diff' | 'provenance'

/**
 * Geteilte Versions-Insel (Track A): Liste mit Status-Badges plus Restore-,
 * Diff- und Provenance-Aktionen je Version. Entity-agnostisch — die vier
 * Detail-Pages reichen die jeweiligen API-Callbacks herein.
 */
export function VersionHistory({
  versions,
  canEdit,
  onRestore,
  loadDiff,
  loadProvenance,
}: VersionHistoryProps) {
  const { t } = useTranslation('version')
  const [openPanel, setOpenPanel] = useState<{ version: number; kind: PanelKind } | null>(null)
  const [diff, setDiff] = useState<VersionDiff | null>(null)
  const [provenance, setProvenance] = useState<ProvenanceEntry[] | null>(null)
  const [panelLoading, setPanelLoading] = useState(false)
  const [panelError, setPanelError] = useState<string | null>(null)
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null)

  const hasDraft = versions.some((version) => version.status === 'draft')

  const togglePanel = async (version: number, kind: PanelKind) => {
    if (openPanel?.version === version && openPanel.kind === kind) {
      setOpenPanel(null)
      return
    }
    setOpenPanel({ version, kind })
    setPanelLoading(true)
    setPanelError(null)
    setDiff(null)
    setProvenance(null)
    try {
      if (kind === 'diff') {
        setDiff(await loadDiff(version))
      } else {
        setProvenance(await loadProvenance(version))
      }
    } catch (cause) {
      setPanelError(cause instanceof Error ? cause.message : t('history.loadFailed'))
    } finally {
      setPanelLoading(false)
    }
  }

  const restore = async (version: number) => {
    setRestoringVersion(version)
    try {
      await onRestore(version)
      setOpenPanel(null)
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : t('history.restoreFailed'))
    } finally {
      setRestoringVersion(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('history.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2" aria-label={t('history.listLabel')}>
          {versions.map((version) => {
            const isOpen = openPanel?.version === version.version
            return (
              <li
                key={version.version}
                className="rounded-lg border border-border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <span className="font-medium">v{version.version}</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(version.created_at).toLocaleString()}
                    </span>
                    <StatusBadge status={version.status} />
                  </span>
                  <span className="flex flex-wrap items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-pressed={isOpen && openPanel?.kind === 'diff'}
                      onClick={() => void togglePanel(version.version, 'diff')}
                    >
                      {t('history.diff')}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-pressed={isOpen && openPanel?.kind === 'provenance'}
                      onClick={() => void togglePanel(version.version, 'provenance')}
                    >
                      {version.status === 'active' ? t('history.whyActive') : t('history.history')}
                    </Button>
                    {canEdit ? (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={hasDraft || restoringVersion !== null}
                        title={
                          hasDraft ? t('history.restoreBlockedHint') : t('history.restoreHint')
                        }
                        onClick={() => void restore(version.version)}
                      >
                        {t('common:actions.restore')}
                      </Button>
                    ) : null}
                  </span>
                </div>
                {isOpen ? (
                  <div className="mt-3 border-t border-border pt-3">
                    {panelLoading ? (
                      <p className="text-sm text-muted-foreground">{t('common:loading')}</p>
                    ) : panelError !== null ? (
                      <p className="text-sm text-destructive">{panelError}</p>
                    ) : openPanel?.kind === 'diff' && diff !== null ? (
                      <VersionDiffView diff={diff} />
                    ) : openPanel?.kind === 'provenance' && provenance !== null ? (
                      <ProvenanceList entries={provenance} />
                    ) : null}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
