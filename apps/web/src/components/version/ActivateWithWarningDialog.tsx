import { HelpCircle, XCircle } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, type VersionTransitionOptions } from '@/api/client'
import type { TestReport, TestReportEntry, VersionedEntityType } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

// Aktivieren mit Warnung (Lernschleife B5, Spec S11, ADR-0053 6.3).
//
// Der Server verlangt fuer `review -> active` bei roten oder fehlenden
// Pruefergebnissen `acknowledge_test_report: true` UND einen (getrimmt) nicht
// leeren `override_reason` (`version_status.check_activation_contract`). Die
// UI spiegelt genau diese Bedingung: `counts.passed < counts.total` fuehrt
// ueber diesen Dialog, alles andere aktiviert wie bisher mit einem Klick.
// Entschieden (Owner/PM 2026-09-28): Grund nach Trimmen 1 bis 1 000 Zeichen,
// keine 10-Zeichen-Mindestlaenge.

/** Obergrenze des Grunds nach Trimmen (Server: `OVERRIDE_REASON_MAX_LENGTH`). */
const OVERRIDE_REASON_MAX_LENGTH = 1000

/** Die beiden 409-Gruende des Aktivierungsvertrags (ADR-0053 6.3). */
const CONTRACT_REASONS = new Set(['test_results_incomplete', 'test_override_reason_required'])

function contractReason(cause: unknown): string | null {
  if (!(cause instanceof ApiError) || cause.status !== 409) return null
  const body = cause.body
  if (typeof body !== 'object' || body === null) return null
  const reason = (body as { reason?: unknown }).reason
  return typeof reason === 'string' && CONTRACT_REASONS.has(reason) ? reason : null
}

export interface ActivateWithWarningDialogProps {
  /** Bericht der Zielversion; `null` = konnte nicht geladen werden (alle gelten als fehlend). */
  report: TestReport | null
  disabled?: boolean
  testId?: string
  /**
   * Aktiviert mit Bestaetigung und Grund. Muss bei Fehlschlag werfen — der
   * Dialog zeigt den Fehler dann selbst an und bleibt offen.
   */
  onConfirm: (reason: string) => Promise<void>
}

export function ActivateWithWarningDialog({
  report,
  disabled = false,
  testId,
  onConfirm,
}: ActivateWithWarningDialogProps) {
  const { t } = useTranslation('learning')
  const reasonId = useId()
  const hintId = useId()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ title: string; message: string } | null>(null)

  const trimmed = reason.trim()
  const tooLong = trimmed.length > OVERRIDE_REASON_MAX_LENGTH
  const canSubmit = trimmed.length > 0 && !tooLong && !busy

  const openChange = (next: boolean) => {
    if (busy) return
    setOpen(next)
    if (!next) {
      setError(null)
    }
  }

  const submit = async () => {
    // Doppelte Sicherung zum gesperrten Knopf: ohne Grund geht nichts raus.
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      await onConfirm(trimmed)
      setOpen(false)
      setReason('')
    } catch (cause: unknown) {
      const code = contractReason(cause)
      if (code !== null) {
        setError({
          title: t(`activateWarning.error.${code}.title`),
          message: t(`activateWarning.error.${code}.body`),
        })
      } else {
        setError({
          title: t('activateWarning.error.generic'),
          message: cause instanceof Error ? cause.message : t('common:errors.unknown'),
        })
      }
    } finally {
      setBusy(false)
    }
  }

  // Ein Pruefall kann mehreren Agenten zugeordnet sein — je Fall einmal listen.
  const openEntries = new Map<string, TestReportEntry>()
  for (const group of report?.agents ?? []) {
    for (const entry of group.entries) {
      if (entry.state !== 'pass') openEntries.set(entry.test_case.id, entry)
    }
  }
  const failed = [...openEntries.values()].filter((entry) => entry.state !== 'missing')
  const missing = [...openEntries.values()].filter((entry) => entry.state === 'missing')

  return (
    <Dialog open={open} onOpenChange={openChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="brand" disabled={disabled} data-testid={testId}>
          {t('activateWarning.trigger')}
        </Button>
      </DialogTrigger>
      <DialogContent data-testid="activate-warning-dialog">
        <DialogHeader>
          <DialogTitle>{t('activateWarning.title')}</DialogTitle>
          <DialogDescription>
            {report === null
              ? t('activateWarning.descriptionUnknown')
              : t('activateWarning.description', {
                  failed: report.counts.failed + report.counts.error,
                  missing: report.counts.missing,
                  total: report.counts.total,
                })}
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-w-0 flex-col gap-4">
          {report === null ? (
            <p className="flex items-start gap-2 text-sm text-destructive">
              <HelpCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <span>{t('activateWarning.reportUnavailable')}</span>
            </p>
          ) : (
            <>
              <CaseList
                heading={t('activateWarning.failedHeading', { count: failed.length })}
                entries={failed}
              />
              <CaseList
                heading={t('activateWarning.missingHeading', { count: missing.length })}
                entries={missing}
              />
            </>
          )}
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor={reasonId}>
              {t('activateWarning.reasonLabel')}
              <span aria-hidden="true"> *</span>
            </Label>
            <Textarea
              id={reasonId}
              rows={3}
              required
              aria-required="true"
              aria-describedby={hintId}
              aria-invalid={tooLong || undefined}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              disabled={busy}
              className="w-full"
            />
            <p id={hintId} className="text-xs text-muted-foreground">
              {t('activateWarning.reasonHint')}
            </p>
            {tooLong ? (
              <p className="text-xs text-destructive" data-testid="activate-warning-too-long">
                {t('activateWarning.reasonTooLong', { max: OVERRIDE_REASON_MAX_LENGTH })}
              </p>
            ) : null}
          </div>
          {error !== null ? <ErrorAlert title={error.title} message={error.message} /> : null}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={!canSubmit}
            aria-busy={busy || undefined}
            data-testid="activate-warning-confirm"
            onClick={() => void submit()}
          >
            {t('activateWarning.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CaseList({ heading, entries }: { heading: string; entries: TestReportEntry[] }) {
  const { t } = useTranslation('learning')
  if (entries.length === 0) return null
  return (
    <section className="flex min-w-0 flex-col gap-1.5" aria-label={heading}>
      <p className="text-sm font-medium">{heading}</p>
      <ul className="flex min-w-0 flex-col gap-1.5">
        {entries.map((entry) => {
          const isMissing = entry.state === 'missing'
          const Icon = isMissing ? HelpCircle : XCircle
          const runs =
            entry.result !== null ? `${entry.result.runs_passed}/${entry.result.runs_total}` : null
          return (
            <li
              key={entry.test_case.id}
              className="flex min-w-0 items-start gap-2 text-sm"
              data-testid="activate-warning-case"
              data-state={entry.state}
            >
              <Icon
                className={cn(
                  'mt-0.5 size-4 shrink-0',
                  isMissing ? 'text-muted-foreground' : 'text-destructive',
                )}
                aria-hidden="true"
              />
              <span className="min-w-0 break-words">
                <span className={isMissing ? 'text-muted-foreground' : 'text-destructive'}>
                  {t(`testResults.kind.${entry.state}`)}
                </span>
                {': '}
                {entry.test_case.title}
                {runs !== null ? ` (${runs})` : ''}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export interface ActivateWithTestReportProps {
  entityType: VersionedEntityType
  /** UUID der Zielversion (`*Version.id`). */
  versionId: string
  /** Text des Knopfs im gruenen Fall (Default-Label der Leiste). */
  label: string
  disabled: boolean
  testId?: string
  /** Gruener Fall: aktiviert wie bisher mit einem Klick (Leiste behandelt Fehler). */
  onActivate: () => void
  /** Roter/fehlender Fall: Transition mit Bestaetigung und Grund; wirft bei Fehlschlag. */
  onActivateWithOverride: (options: VersionTransitionOptions) => Promise<void>
}

/**
 * Laedt den Pruefbericht der Zielversion und waehlt den Weg: alles bestanden
 * (oder keine Pruefaelle) = normaler Knopf, sonst „Aktivieren…“ mit Dialog.
 * Wird nur von Admins gerendert — die Leisten zeigen Nicht-Admins den
 * gesperrten Knopf ohne Bericht-Request.
 */
export function ActivateWithTestReport({
  entityType,
  versionId,
  label,
  disabled,
  testId,
  onActivate,
  onActivateWithOverride,
}: ActivateWithTestReportProps) {
  const { t } = useTranslation('learning')
  const api = useApi()
  // Ergebnis mit Schluessel: wechselt die Zielversion, gilt das alte Ergebnis
  // nicht mehr und der Knopf zeigt wieder „laedt“ — ohne synchrones setState
  // im Effekt.
  const key = `${entityType}:${versionId}`
  const [result, setResult] = useState<
    { key: string; kind: 'loaded'; report: TestReport } | { key: string; kind: 'failed' } | null
  >(null)

  useEffect(() => {
    let cancelled = false
    api
      .getTestReport(entityType, versionId)
      .then((report) => {
        if (!cancelled) setResult({ key: `${entityType}:${versionId}`, kind: 'loaded', report })
      })
      .catch(() => {
        // Spec S11: ohne Bericht gelten alle Pruefaelle als „fehlt“.
        if (!cancelled) setResult({ key: `${entityType}:${versionId}`, kind: 'failed' })
      })
    return () => {
      cancelled = true
    }
  }, [api, entityType, versionId])

  const state = result !== null && result.key === key ? result : { kind: 'loading' as const }

  if (state.kind === 'loading') {
    return (
      <Button type="button" variant="brand" disabled aria-busy="true" data-testid={testId}>
        {label}
      </Button>
    )
  }

  if (state.kind === 'loaded' && state.report.counts.passed >= state.report.counts.total) {
    const total = state.report.counts.total
    return (
      <>
        {total > 0 ? (
          <p className="basis-full text-sm text-muted-foreground" data-testid="activate-all-passed">
            {t('activateWarning.allPassed', { count: total })}
          </p>
        ) : null}
        <Button
          type="button"
          variant="brand"
          disabled={disabled}
          data-testid={testId}
          onClick={onActivate}
        >
          {label}
        </Button>
      </>
    )
  }

  return (
    <ActivateWithWarningDialog
      report={state.kind === 'loaded' ? state.report : null}
      disabled={disabled}
      testId={testId}
      onConfirm={(reason) =>
        onActivateWithOverride({ acknowledge_test_report: true, override_reason: reason })
      }
    />
  )
}

/** Sichtbarer Grund neben dem gesperrten Aktivieren-Knopf (Spec S11). */
export function AdminOnlyHint() {
  const { t } = useTranslation('common')
  return (
    <span className="text-sm text-muted-foreground" data-testid="activate-admin-only">
      {t('statusBar.adminOnlyHint')}
    </span>
  )
}
