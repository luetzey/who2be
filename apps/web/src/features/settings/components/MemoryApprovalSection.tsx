import { Eye, Info, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type {
  MemoryAutoCell,
  MemoryAutoPolicyRead,
  MemoryAutoRow,
  MemoryGuardMode,
  MemoryOrigin,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import {
  AutoApprovalLimitsDialog,
  AutoApprovalLimitsList,
  MEMORY_AUTO_EXPIRY_DAYS,
} from './AutoApprovalLimitsDialog'

// Lernschleife C6 — Workspace-Einstellung „Automatische Freigabe“ (Spec S4,
// Delta S4, ADR-0053 4.1–4.3). Die Matrix Art x Herkunft wird aus Serverdaten
// gebaut: schaltbar ist genau, was `switchable_cells` nennt; die UI kodiert
// keine eigene Sperrliste. Gesperrte Zellen zeigen „Immer prüfen“ ohne
// Bedienelement, nie ein Schloss oder einen Haken (ADR 4.3). Einschalten geht
// nur ueber den Dialog mit den acht Grenzen (S4a). Nur fuer admin — der Parent
// rendert den Abschnitt ausschliesslich fuer Admins, der Server sperrt
// zusaetzlich jeden API-Token (403).

// Zeilen der Tabelle in Spec-Reihenfolge; `lesson` folgt als eigene Zeile, weil
// sie nie in einen Prompt wirkt (eine Aussage fuer alle Herkuenfte).
const ROWS: readonly MemoryAutoRow[] = [
  'user_fact',
  'user_fact_instruction',
  'agent_note',
  'proposal',
]
// `legacy_unknown` bekommt keine Spalte: `origin` ist fuer neue Eintraege
// Pflicht (Delta S4, ADR 6.4).
const ORIGINS: readonly MemoryOrigin[] = ['user_stated', 'inferred', 'external_content']

type LockedReason =
  | 'inferred'
  | 'external_content'
  | 'instruction'
  | 'agent_note'
  | 'proposal'
  | 'generic'

// Sperrgrund aus dem Locale (Delta S4: der Server liefert kein `locked_reason`).
// Die Art geht vor der Herkunft — eine Agentennotiz ist auch „von dir gesagt“
// nie automatisch.
function lockedReason(row: MemoryAutoRow, origin: MemoryOrigin): LockedReason {
  if (row === 'user_fact_instruction') return 'instruction'
  if (row === 'agent_note') return 'agent_note'
  if (row === 'proposal') return 'proposal'
  if (origin === 'inferred' || origin === 'external_content') return origin
  return 'generic'
}

function sameCell(a: MemoryAutoCell, b: MemoryAutoCell): boolean {
  return a.row === b.row && a.origin === b.origin
}

function hasCell(cells: readonly MemoryAutoCell[], cell: MemoryAutoCell): boolean {
  return cells.some((entry) => sameCell(entry, cell))
}

function describeError(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message !== '' ? cause.message : fallback
}

interface CellSwitchProps {
  checked: boolean
  disabled: boolean
  labelledBy: string
  onToggle: () => void
}

// Schalter als `role="switch"` (Spec S4). Bewusst ohne Haken-Icon (ADR 4.3):
// der Zustand steht als Wort daneben, Farbe ist nie die einzige Information.
function CellSwitch({ checked, disabled, labelledBy, onToggle }: CellSwitchProps) {
  const { t } = useTranslation('learning')
  return (
    <Button
      type="button"
      variant="ghost"
      role="switch"
      aria-checked={checked}
      aria-labelledby={labelledBy}
      disabled={disabled}
      onClick={onToggle}
      className="h-auto min-h-8 gap-2 px-1 font-normal hover:bg-transparent"
    >
      <span
        aria-hidden="true"
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors duration-[var(--duration-fast)] ease-standard',
          checked ? 'border-primary bg-primary' : 'border-input bg-muted',
        )}
      >
        <span
          className={cn(
            'inline-block size-4 rounded-full bg-background shadow-card transition-transform duration-[var(--duration-fast)] ease-standard',
            checked ? 'translate-x-4' : 'translate-x-0.5',
          )}
        />
      </span>
      <span aria-hidden="true">{checked ? t('autoPolicy.on') : t('autoPolicy.off')}</span>
    </Button>
  )
}

interface LockedCellProps {
  reason: LockedReason
  tooltipLabel: string
}

// Gesperrte Zelle: Icon `Eye` + „Immer prüfen“ (Delta §0 ersetzt `Lock`),
// kein deaktiviertes Bedienelement. Der Grund steht per Tooltip und fuer
// Screenreader zusaetzlich als Text in der Zelle.
function LockedCell({ reason, tooltipLabel }: LockedCellProps) {
  const { t } = useTranslation('learning')
  const text = t(`autoPolicy.locked.${reason}`)
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground" data-locked-cell>
      <Eye className="size-4 shrink-0" aria-hidden="true" />
      <span>{t('autoPolicy.alwaysReview')}</span>
      <span className="sr-only">{text}</span>
      <InfoTooltip label={tooltipLabel}>{text}</InfoTooltip>
    </span>
  )
}

export function MemoryApprovalSection() {
  const { t } = useTranslation('learning')
  const api = useApi()
  const isMobile = useIsMobile()
  const baseId = useId()

  const [policy, setPolicy] = useState<MemoryAutoPolicyRead | null>(null)
  const [guardMode, setGuardMode] = useState<MemoryGuardMode | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [pendingCell, setPendingCell] = useState<MemoryAutoCell | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    setForbidden(false)
    try {
      const next = await api.getMemoryAutoPolicy()
      setPolicy(next)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 403) {
        setForbidden(true)
      } else {
        setLoadError(describeError(cause, t('autoPolicy.loadError')))
      }
    } finally {
      setLoading(false)
    }
    // Der Waechter-Modus steuert nur den Hinweis-Banner; ein Fehler hier darf
    // die Matrix nicht blockieren.
    try {
      const guard = await api.getMemoryGuard()
      setGuardMode(guard.mode)
    } catch {
      setGuardMode(null)
    }
  }, [api, t])

  useEffect(() => {
    void load()
  }, [load])

  async function save(enabled: MemoryAutoCell[], toast: string) {
    setSaving(true)
    setSaveError(null)
    try {
      // Kein optimistisches Setzen: bei einem Fehler bleibt die Zelle auf dem
      // letzten Serverstand. Die Antwort ist die wirksame Einstellung.
      const saved = await api.updateMemoryAutoPolicy({ enabled_cells: enabled })
      setPolicy(saved)
      notify.success(toast)
    } catch (cause) {
      setSaveError(describeError(cause, t('autoPolicy.saveError')))
    } finally {
      setSaving(false)
      setPendingCell(null)
    }
  }

  function onToggle(cell: MemoryAutoCell) {
    if (policy === null) return
    if (hasCell(policy.enabled_cells, cell)) {
      // Ausschalten geht sofort, mit Toast (Spec S4).
      void save(
        policy.enabled_cells.filter((entry) => !sameCell(entry, cell)),
        t('autoPolicy.toastOff'),
      )
      return
    }
    // Einschalten nur ueber den Dialog mit allen acht Punkten (ADR 4.3).
    setPendingCell(cell)
  }

  function onConfirmEnable() {
    if (policy === null || pendingCell === null) return
    void save([...policy.enabled_cells, pendingCell], t('autoPolicy.toastOn'))
  }

  const rowLabelId = (row: MemoryAutoRow) => `${baseId}-row-${row}`
  const originLabelId = (origin: MemoryOrigin) => `${baseId}-origin-${origin}`

  function renderCell(row: MemoryAutoRow, origin: MemoryOrigin, originLabel: string) {
    if (policy === null) return null
    const cell: MemoryAutoCell = { row, origin }
    if (hasCell(policy.switchable_cells, cell)) {
      return (
        <CellSwitch
          checked={hasCell(policy.enabled_cells, cell)}
          disabled={saving}
          labelledBy={`${rowLabelId(row)} ${originLabel}`}
          onToggle={() => onToggle(cell)}
        />
      )
    }
    return (
      <LockedCell
        reason={lockedReason(row, origin)}
        tooltipLabel={t('autoPolicy.reasonLabel', {
          row: t(`autoPolicy.row.${row}`),
          origin: t(`autoPolicy.origin.${origin}`),
        })}
      />
    )
  }

  // Unter `md` wird die Matrix zur Liste je Art (Spec S4, 390 px). Sind alle
  // Zellen einer Zeile gesperrt und teilen denselben Grund, steht die Zeile
  // zusammengefasst als „Alle Herkünfte“.
  function renderMobileRow(row: MemoryAutoRow) {
    if (policy === null) return null
    const reasons = ORIGINS.map((origin) => lockedReason(row, origin))
    const collapsible =
      ORIGINS.every((origin) => !hasCell(policy.switchable_cells, { row, origin })) &&
      reasons.every((reason) => reason === reasons[0])
    return (
      <li key={row} className="flex flex-col gap-1 border-t pt-3 first:border-t-0 first:pt-0">
        <span id={rowLabelId(row)} className="text-sm font-medium">
          {t(`autoPolicy.row.${row}`)}
        </span>
        {collapsible ? (
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pl-3">
            <span className="text-sm">{t('autoPolicy.allOrigins')}</span>
            <LockedCell
              reason={reasons[0]}
              tooltipLabel={t('autoPolicy.reasonLabelRow', { row: t(`autoPolicy.row.${row}`) })}
            />
          </div>
        ) : (
          ORIGINS.map((origin) => (
            <div
              key={origin}
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pl-3"
            >
              <span id={`${originLabelId(origin)}-${row}`} className="min-w-0 text-sm break-words">
                {t(`autoPolicy.origin.${origin}`)}
              </span>
              {renderCell(row, origin, `${originLabelId(origin)}-${row}`)}
            </div>
          ))
        )}
      </li>
    )
  }

  const anyEnabled = (policy?.enabled_cells.length ?? 0) > 0

  return (
    <Card id="memory-approval" className="scroll-mt-20">
      <CardHeader>
        <CardTitle>{t('autoPolicy.sectionTitle')}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold tracking-tight">{t('autoPolicy.title')}</h2>
          <p className="text-sm text-muted-foreground">{t('autoPolicy.intro')}</p>
        </div>

        {loading ? <LoadingState rows={4} /> : null}
        {!loading && forbidden ? (
          <p className="text-sm text-muted-foreground">{t('autoPolicy.humanOnly')}</p>
        ) : null}
        {!loading && loadError !== null ? <ErrorAlert message={loadError} /> : null}

        {!loading && policy !== null ? (
          <>
            {anyEnabled && guardMode === 'off' ? (
              <AttentionBanner
                variant="destructive"
                icon={TriangleAlert}
                title={t('autoPolicy.guardOff.title')}
                description={t('autoPolicy.guardOff.description')}
                actions={
                  // Sprung zum Waechter auf derselben Seite. `Link` mit Hash
                  // aendert die URL, scrollt aber nicht von selbst (Router-
                  // Navigation) — deshalb scrollt der Klick selbst dorthin.
                  <Button asChild variant="outline" size="sm">
                    <Link
                      to={{ hash: '#memory-guard' }}
                      onClick={() => {
                        const target = document.getElementById('memory-guard')
                        target?.scrollIntoView({ block: 'start' })
                      }}
                    >
                      {t('autoPolicy.guardOff.action')}
                    </Link>
                  </Button>
                }
              />
            ) : null}

            {isMobile ? (
              <ul className="flex flex-col gap-3" aria-label={t('autoPolicy.matrixCaption')}>
                {ROWS.map((row) => renderMobileRow(row))}
                <li className="flex flex-col gap-1 border-t pt-3">
                  <span className="text-sm font-medium">{t('autoPolicy.row.lesson')}</span>
                  <span className="inline-flex items-center gap-1.5 pl-3 text-sm text-muted-foreground">
                    {t('autoPolicy.lessonNever')}
                    <InfoTooltip label={t('autoPolicy.reasonLabelRow', { row: t('autoPolicy.row.lesson') })}>
                      {t('autoPolicy.locked.lesson')}
                    </InfoTooltip>
                  </span>
                </li>
              </ul>
            ) : (
              <table className="w-full table-fixed border-collapse text-left text-sm">
                <caption className="sr-only">{t('autoPolicy.matrixCaption')}</caption>
                <thead>
                  <tr className="border-b">
                    <th scope="col" className="w-1/4 py-2 pr-3 font-medium text-muted-foreground">
                      {t('autoPolicy.kindHeader')}
                    </th>
                    {ORIGINS.map((origin) => (
                      <th
                        key={origin}
                        scope="col"
                        id={originLabelId(origin)}
                        className="py-2 pr-3 align-bottom font-medium break-words"
                      >
                        {t(`autoPolicy.origin.${origin}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr key={row} className="border-b">
                      <th
                        scope="row"
                        id={rowLabelId(row)}
                        className="py-2 pr-3 align-middle font-medium break-words"
                      >
                        {t(`autoPolicy.row.${row}`)}
                      </th>
                      {ORIGINS.map((origin) => (
                        <td key={origin} className="py-2 pr-3 align-middle">
                          {renderCell(row, origin, originLabelId(origin))}
                        </td>
                      ))}
                    </tr>
                  ))}
                  <tr>
                    <th scope="row" className="py-2 pr-3 align-middle font-medium">
                      {t('autoPolicy.row.lesson')}
                    </th>
                    <td colSpan={ORIGINS.length} className="py-2 pr-3 align-middle">
                      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                        {t('autoPolicy.lessonNever')}
                        <InfoTooltip
                          label={t('autoPolicy.reasonLabelRow', { row: t('autoPolicy.row.lesson') })}
                        >
                          {t('autoPolicy.locked.lesson')}
                        </InfoTooltip>
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            )}

            {saveError !== null ? <ErrorAlert message={saveError} /> : null}

            <div className="space-y-1 text-sm text-muted-foreground">
              <p>{t('autoPolicy.legacyAuto')}</p>
              <p>{t('autoPolicy.humanChannel')}</p>
              <p>{t('autoPolicy.expiry', { days: MEMORY_AUTO_EXPIRY_DAYS })}</p>
            </div>

            {/* Dauerhafte Fassung der Liste aus S4a, ohne Checkbox. */}
            <details className="group rounded-md border p-3" data-testid="auto-approval-limits-disclosure">
              <summary className="flex min-h-8 cursor-pointer items-center gap-2 text-sm font-medium">
                <Info className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                {t('autoPolicy.limits.disclosure')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <AutoApprovalLimitsList />
                <p className="text-sm text-muted-foreground">
                  {t('autoPolicy.limits.stillHappens', { days: MEMORY_AUTO_EXPIRY_DAYS })}
                </p>
              </div>
            </details>

            <AutoApprovalLimitsDialog
              open={pendingCell !== null}
              onOpenChange={(open) => {
                if (!open && !saving) setPendingCell(null)
              }}
              onConfirm={onConfirmEnable}
              busy={saving}
            />
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
