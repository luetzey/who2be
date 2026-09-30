import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'

import type {
  ProvenanceEntry,
  VersionDiff,
  VersionedEntityType,
  VersionStatus,
} from '@/api/types'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'

import { ProvenanceList } from './ProvenanceList'
import { TestResultsPanel } from './TestResultsPanel'
import { VersionDiffView } from './VersionDiffView'

export interface VersionHistoryItem {
  version: number
  /** UUID der Version — noetig fuer den Pruefbericht (`*VersionRead.id`). */
  id?: string
  status?: VersionStatus
  created_at: string
}

interface VersionHistoryProps {
  versions: VersionHistoryItem[]
  /** Editor+ darf Restore auslösen (Backend-Gate: editor). */
  canEdit: boolean
  /** Stellt die Version als neue Draft wieder her (Page wired API + reload). */
  onRestore: (version: number) => Promise<void>
  /**
   * Lädt den read-only Diff der Version gegen die aktive Version. Optional —
   * Entities ohne `/versions/{version}/diff`-Endpoint (z. B. ExternalTool,
   * WP-4) lassen den Prop weg; der Diff-Button entfällt dann.
   */
  loadDiff?: (version: number) => Promise<VersionDiff>
  /** Lädt die Status-Historie der Version ("warum aktiv"). */
  loadProvenance: (version: number) => Promise<ProvenanceEntry[]>
  /**
   * Deep-Link `?diff=<n>` (Audit E1 = A): der Diff dieser Version ist beim
   * Oeffnen bereits aufgeklappt. Ohne passende Version bzw. ohne `loadDiff`
   * ohne Wirkung.
   */
  initialDiffVersion?: number
  /**
   * Lernschleife B5 (Spec S11): Elementart fuer den Pruefbericht. Gesetzt
   * zeigt der aufgeklappte Diff die Pruefall-Ergebnisse der Version daneben.
   * Ohne Wert bleibt die Insel wie bisher.
   */
  testReportEntityType?: VersionedEntityType
  /** Query zum Tab „Prüffälle“ fuer den Leerzustand (z. B. `?tab=tests`). */
  testCasesSearch?: string
}

type PanelKind = 'diff' | 'provenance'

// Audit A2: der gedrueckte Zustand der Panel-Knoepfe (Diff/Historie) muss
// ohne Hover sichtbar sein — gefuellte Flaeche plus Innenkante statt allein
// `aria-pressed`. Brand-Tinte bleibt dem CTA vorbehalten (§8).
const PRESSED_CLASS =
  'aria-pressed:bg-accent aria-pressed:text-accent-foreground aria-pressed:ring-1 aria-pressed:ring-inset aria-pressed:ring-foreground/30'

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
  initialDiffVersion,
  testReportEntityType,
  testCasesSearch,
}: VersionHistoryProps) {
  const { t } = useTranslation('version')
  const diffColumn = useRef<HTMLDivElement | null>(null)
  const [openPanel, setOpenPanel] = useState<{ version: number; kind: PanelKind } | null>(null)
  const [diff, setDiff] = useState<VersionDiff | null>(null)
  const [provenance, setProvenance] = useState<ProvenanceEntry[] | null>(null)
  const [panelLoading, setPanelLoading] = useState(false)
  const [panelError, setPanelError] = useState<string | null>(null)
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null)

  const hasDraft = versions.some((version) => version.status === 'draft')

  const showPanel = async (version: number, kind: PanelKind) => {
    setOpenPanel({ version, kind })
    setPanelLoading(true)
    setPanelError(null)
    setDiff(null)
    setProvenance(null)
    try {
      if (kind === 'diff' && loadDiff !== undefined) {
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

  const togglePanel = async (version: number, kind: PanelKind) => {
    if (openPanel?.version === version && openPanel.kind === kind) {
      setOpenPanel(null)
      return
    }
    await showPanel(version, kind)
  }

  // Deep-Link (Audit E1 = A): den Diff der angefragten Version vorab
  // aufklappen — einmal je Navigation. Jeder Klick auf „Aenderungen ansehen"
  // ist eine neue Navigation mit neuem `location.key` (React Router ersetzt
  // auch bei identischer URL den History-Eintrag), daher oeffnet derselbe Link
  // den Diff wieder, nachdem die Nutzerin ihn zugeklappt hat. Unbekannte
  // Versionen und Entities ohne Diff-Endpoint ignorieren den Wunsch still.
  const { key: navigationKey } = useLocation()
  const autoOpened = useRef<string | undefined>(undefined)
  const targetRow = useRef<HTMLLIElement | null>(null)
  const canOpenInitial =
    initialDiffVersion !== undefined &&
    loadDiff !== undefined &&
    versions.some((version) => version.version === initialDiffVersion)
  useEffect(() => {
    if (initialDiffVersion === undefined) {
      autoOpened.current = undefined
      return
    }
    const request = `${initialDiffVersion}@${navigationKey}`
    if (!canOpenInitial || autoOpened.current === request) return
    autoOpened.current = request
    void showPanel(initialDiffVersion, 'diff')
    // Auf dem Phone liegt die Versionsliste unter dem Falz (Audit A13) —
    // die angesprungene Zeile in den Blick holen. jsdom kennt die Methode nicht.
    targetRow.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
    // showPanel ist bewusst nicht in den Deps: es wechselt je Render die
    // Identitaet, der Effekt soll aber nur auf einen neuen Wunsch reagieren.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialDiffVersion, canOpenInitial, navigationKey])

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
            // Pruefbericht nur, wenn die Seite ihn anfordert und die Version
            // ihre UUID mitbringt (`*VersionRead.id`).
            const reportVersionId =
              testReportEntityType !== undefined ? (version.id ?? null) : null
            const panelContent = panelLoading ? (
              <p className="text-sm text-muted-foreground">{t('common:loading')}</p>
            ) : panelError !== null ? (
              <p className="text-sm text-destructive">{panelError}</p>
            ) : openPanel?.kind === 'diff' && diff !== null ? (
              <VersionDiffView diff={diff} />
            ) : openPanel?.kind === 'provenance' && provenance !== null ? (
              <ProvenanceList entries={provenance} />
            ) : null
            return (
              <li
                key={version.version}
                ref={version.version === initialDiffVersion ? targetRow : undefined}
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
                    {loadDiff !== undefined ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className={PRESSED_CLASS}
                        aria-pressed={isOpen && openPanel?.kind === 'diff'}
                        onClick={() => void togglePanel(version.version, 'diff')}
                      >
                        {t('history.diff')}
                      </Button>
                    ) : null}
                    <Button
                      variant="ghost"
                      size="sm"
                      className={PRESSED_CLASS}
                      aria-pressed={isOpen && openPanel?.kind === 'provenance'}
                      onClick={() => void togglePanel(version.version, 'provenance')}
                    >
                      {version.status === 'active' ? t('history.whyActive') : t('history.history')}
                    </Button>
                    {canEdit ? (
                      <Button
                        variant="ghost"
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
                    {openPanel?.kind === 'diff' &&
                    testReportEntityType !== undefined &&
                    reportVersionId !== null ? (
                      // Spec S11: Pruefaelle neben dem Diff (ab lg zwei
                      // Spalten); darunter gestapelt, Pruefaelle zuerst. Beide
                      // laden getrennt — ein Fehler rechts blockiert den Diff
                      // nicht.
                      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
                        <div
                          ref={diffColumn}
                          tabIndex={-1}
                          className="order-last min-w-0 outline-none lg:order-first"
                        >
                          {panelContent}
                        </div>
                        <div className="order-first min-w-0 lg:order-last">
                          <TestResultsPanel
                            entityType={testReportEntityType}
                            versionId={reportVersionId}
                            version={version.version}
                            testCasesSearch={testCasesSearch}
                            onJumpToDiff={() => diffColumn.current?.focus()}
                          />
                        </div>
                      </div>
                    ) : (
                      panelContent
                    )}
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
