import {
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Copy,
  Eye,
  HelpCircle,
  Info,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type {
  Member,
  TestReport,
  TestReportAgentGroup,
  TestReportEntry,
  TestRunRead,
  TestVerdict,
  VersionedEntityType,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ExpandableText } from '@/components/data/ExpandableText'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

// Pruefall-Ergebnisse einer Elementversion neben dem Diff (Lernschleife B5,
// Spec S11, ADR-0053 6.2). Nur Anzeige und menschliche Bewertung — das
// Aktivieren selbst bleibt in der Statusleiste (Paket B5-Dialog).
//
// - Der Bericht kommt fertig vom Server (`GET /versions/{type}/{id}/test-
//   report`): Menge nach ADR 3.2.1, gruppiert nach Agent mit `via`, je
//   Pruefall das LETZTE Ergebnis fuer genau diese Version oder `missing`.
//   Laeufe gegen andere Versionen stehen nicht im Bericht; sie zaehlen als
//   „kein Ergebnis“.
// - `pass` gibt es nur bei n/n Laeufen — der Server erzwingt das beim
//   Melden; die Zeile zeigt `k/n` zusaetzlich zum Wort.
// - `attestation` ist immer sichtbar: `client_self_report` = Selbstauskunft
//   des Clients, `human_rating` = Bewertung durch einen Menschen (Name aus
//   der Mitgliederliste). Freitext (Eingabe, Erwartung, Ausgabe) wird als
//   Textknoten mit `break-words` gerendert, nie als HTML (ADR-0038).
// - `human_rule`-Faelle bewertet ein Mensch hier: `POST /test-runs` aus der
//   Session, der Server setzt `human_rating` und `reported_by_user_id`.

/** Anzeige-Zustand einer Ergebniszeile (Spec S11, Tabelle „Ergebnis-Zeilen“). */
type TestResultKind = 'fail' | 'error' | 'missing' | 'awaiting' | 'pass'

/**
 * Ordnet einen Berichtseintrag einem Anzeige-Zustand zu. `human_rule`-Faelle
 * ohne menschliche Bewertung „warten“: der Client-Runner meldet sie nur mit
 * Ausgabe und `verdict='error'` (ADR 3.2), das ist kein Laufzeitfehler.
 */
function resultKind(entry: TestReportEntry): TestResultKind {
  if (entry.state === 'pass') return 'pass'
  if (entry.state === 'missing') {
    return entry.test_case.check_kind === 'human_rule' ? 'awaiting' : 'missing'
  }
  if (
    entry.test_case.check_kind === 'human_rule' &&
    entry.result?.attestation !== 'human_rating'
  ) {
    return 'awaiting'
  }
  return entry.state
}

// Sortierung laut Spec: nicht bestanden -> kein Ergebnis -> wartet -> bestanden.
const KIND_ORDER: Record<TestResultKind, number> = {
  fail: 0,
  error: 1,
  missing: 2,
  awaiting: 3,
  pass: 4,
}

const KIND_ICON: Record<TestResultKind, LucideIcon> = {
  pass: CheckCircle2,
  fail: XCircle,
  error: XCircle,
  missing: HelpCircle,
  awaiting: Eye,
}

// Farbe ist nie die alleinige Information (§11): jede Zeile traegt ihr Wort.
// Rot laeuft ueber `text-destructive` (= `--destructive-text`, Audit A6),
// damit es im Dark Mode lesbar bleibt.
const KIND_ICON_CLASS: Record<TestResultKind, string> = {
  pass: 'text-[var(--status-active)]',
  fail: 'text-destructive',
  error: 'text-destructive',
  missing: 'text-muted-foreground',
  awaiting: 'text-[var(--status-review)]',
}

const KIND_WORD_CLASS: Record<TestResultKind, string> = {
  pass: 'text-foreground',
  fail: 'text-destructive',
  error: 'text-destructive',
  missing: 'text-muted-foreground',
  awaiting: 'text-foreground',
}

/** Ab so vielen bestandenen Faellen je Agent werden sie eingeklappt (Spec S11). */
const COLLAPSE_PASSED_FROM = 5

export interface TestResultsPanelProps {
  entityType: VersionedEntityType
  /** UUID der Version (`*VersionRead.id`). */
  versionId: string
  /** Versionsnummer — fuer den Startsatz „Noch keine Ergebnisse“. */
  version: number
  /**
   * Query fuer den Link „Prüffall anlegen“ im Leerzustand (z. B.
   * `?tab=tests`). Ohne Wert entfaellt der Link — nicht jede Detailseite hat
   * einen Tab „Prüffälle“.
   */
  testCasesSearch?: string
  /** Mobil: Sprung von der Zusammenfassung zum Diff (Spec S11, 390 px). */
  onJumpToDiff?: () => void
}

type LoadError = { kind: 'forbidden' } | { kind: 'message'; message: string }

export function TestResultsPanel({
  entityType,
  versionId,
  version,
  testCasesSearch,
  onJumpToDiff,
}: TestResultsPanelProps) {
  const { t, i18n } = useTranslation('learning')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const isViewer = role === 'viewer'
  const canRate = role === 'editor' || role === 'admin'
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [report, setReport] = useState<TestReport | null>(null)
  const [loading, setLoading] = useState(!isViewer)
  const [error, setError] = useState<LoadError | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  // Agentnamen fuer Melder, die nicht als betroffener Agent im Bericht stehen.
  // `null` = nicht aufloesbar (403/404) -> „Unbekannter Agent“, nie die UUID.
  const [lookedUpAgents, setLookedUpAgents] = useState<ReadonlyMap<string, string | null>>(
    () => new Map(),
  )

  // `getTestReport` nimmt kein AbortSignal an. Jeder Abruf merkt sich daher
  // seine Generation; der Effekt-Cleanup (Unmount, Versionswechsel) zaehlt
  // sie hoch, und eine spaete Antwort einer alten Generation setzt keinen
  // State mehr — auch nicht die eines `reload()`.
  const generation = useRef(0)
  const fetchReport = useCallback(() => {
    const current = generation.current
    const isCurrent = () => current === generation.current
    api
      .getTestReport(entityType, versionId)
      .then((data) => {
        if (!isCurrent()) return
        setReport(data)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (!isCurrent()) return
        if (cause instanceof ApiError && cause.status === 403) {
          setError({ kind: 'forbidden' })
        } else {
          setError({
            kind: 'message',
            message: cause instanceof Error ? cause.message : t('common:errors.unknown'),
          })
        }
      })
      .finally(() => {
        if (isCurrent()) setLoading(false)
      })
  }, [api, entityType, versionId, t])

  useEffect(() => {
    if (!isViewer) fetchReport()
    return () => {
      generation.current += 1
    }
  }, [fetchReport, isViewer])

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchReport()
  }, [fetchReport])

  // Namen fuer „Bewertung durch <Nutzer>“ nur laden, wenn es menschliche
  // Bewertungen gibt. Scheitert das, bleibt die Kurz-ID stehen.
  const hasHumanRatings = useMemo(
    () =>
      report?.agents.some((group) =>
        group.entries.some((entry) => entry.result?.attestation === 'human_rating'),
      ) ?? false,
    [report],
  )
  useEffect(() => {
    if (!hasHumanRatings) return
    let cancelled = false
    api
      .listMembers()
      .then((data) => {
        if (!cancelled) setMembers(data)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [api, hasHumanRatings])

  const tally = useMemo(() => {
    const counts: Record<TestResultKind, number> = {
      fail: 0,
      error: 0,
      missing: 0,
      awaiting: 0,
      pass: 0,
    }
    for (const group of report?.agents ?? []) {
      for (const entry of group.entries) counts[resultKind(entry)] += 1
    }
    return counts
  }, [report])

  const dateTime = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }),
    [i18n.language],
  )

  const userLabel = useCallback(
    (userId: string | null) => {
      if (userId === null) return t('testResults.unknownUser')
      const member = members.find((m) => m.user_id === userId)
      return member?.email || userId.slice(0, 8)
    },
    [members, t],
  )

  // Melder-Agenten: die meisten stehen als betroffener Agent im Bericht.
  // Fehlende einzeln nachschlagen (wie #822); scheitert das, „Unbekannter
  // Agent“ — nie die UUID.
  const reportAgentNames = useMemo(() => {
    const names = new Map<string, string>()
    for (const group of report?.agents ?? []) {
      if (group.agent_name) names.set(group.agent_id, group.agent_name)
    }
    return names
  }, [report])
  const missingReporterIds = useMemo(() => {
    const ids = new Set<string>()
    for (const group of report?.agents ?? []) {
      for (const entry of group.entries) {
        const agentId = entry.result?.reported_by_agent_id
        if (agentId && !reportAgentNames.has(agentId)) ids.add(agentId)
      }
    }
    return [...ids].sort().join(',')
  }, [report, reportAgentNames])
  useEffect(() => {
    if (missingReporterIds === '') return
    let cancelled = false
    const ids = missingReporterIds.split(',')
    void Promise.all(
      ids.map((id) =>
        api
          .getAgent(id)
          .then((agent) => (agent?.id === id && agent.name ? agent.name : null))
          .catch(() => null),
      ),
    ).then((names) => {
      if (cancelled) return
      setLookedUpAgents((prev) => {
        const next = new Map(prev)
        ids.forEach((id, index) => next.set(id, names[index]))
        return next
      })
    })
    return () => {
      cancelled = true
    }
  }, [api, missingReporterIds])

  // Melder eines Ergebnisses: Agentname bzw. Person, `null` = keiner bekannt
  // (Token ohne Agentbindung).
  const reporterLabel = useCallback(
    (result: TestRunRead): string | null => {
      if (result.reported_by_agent_id !== null) {
        const agentId = result.reported_by_agent_id
        return (
          reportAgentNames.get(agentId) ??
          lookedUpAgents.get(agentId) ??
          t('testResults.reporter.unknownAgent')
        )
      }
      if (result.reported_by_user_id !== null) return userLabel(result.reported_by_user_id)
      return null
    },
    [reportAgentNames, lookedUpAgents, userLabel, t],
  )

  const rate = async (entry: TestReportEntry, verdict: TestVerdict) => {
    const passed = verdict === 'pass'
    await api.submitTestRuns({
      subject_entity_type: entityType,
      subject_version_id: versionId,
      results: [
        {
          test_case_id: entry.test_case.id,
          runs_total: 1,
          runs_passed: passed ? 1 : 0,
          verdict,
          // Die bewertete Ausgabe reist mit, damit die Bewertung fuer sich
          // allein nachvollziehbar bleibt (append-only, es zaehlt das letzte).
          output_excerpt: entry.result?.output_excerpt ?? null,
        },
      ],
    })
    notify.success(t(passed ? 'testResults.rate.savedPass' : 'testResults.rate.savedFail'))
    reload()
    // Die Bewertungsknoepfe verschwinden mit dem neuen Zustand — Fokus nie
    // auf `body` fallen lassen (Spec §1 A11y).
    headingRef.current?.focus()
  }

  const total = report?.counts.total ?? 0
  const hasAnyResult =
    report?.agents.some((group) => group.entries.some((entry) => entry.result !== null)) ?? false

  let body
  if (isViewer || error?.kind === 'forbidden') {
    body = (
      <ErrorAlert
        title={t('testCases.forbidden.title')}
        message={t('testCases.forbidden.body', { role: t('testCases.forbidden.role') })}
      />
    )
  } else if (loading && report === null) {
    body = <LoadingState rows={3} />
  } else if (error?.kind === 'message') {
    body = (
      <div className="flex flex-col items-start gap-3">
        <ErrorAlert title={t('testResults.loadFailed')} message={error.message} />
        <Button type="button" variant="outline" onClick={reload}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  } else if (report !== null && total === 0) {
    body = (
      <div className="flex flex-col items-start gap-3 rounded-lg border border-dashed p-4">
        <p className="text-sm">{t('testResults.noCases')}</p>
        {testCasesSearch !== undefined ? (
          <Button asChild variant="outline" size="sm" className="min-h-10 md:min-h-0">
            <Link to={{ search: testCasesSearch }}>
              <ClipboardCheck aria-hidden="true" />
              {t('testCases.create')}
            </Link>
          </Button>
        ) : null}
      </div>
    )
  } else if (report !== null) {
    body = (
      <div className="flex flex-col gap-4">
        {!hasAnyResult ? (
          <NoRunsYet entityType={entityType} entityId={report.entity_id} versionId={versionId} version={version} />
        ) : (
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{t('testResults.clientReported')}</span>
          </p>
        )}
        {report.scope_note === 'no_reference_index' ? (
          <p className="text-sm text-muted-foreground">{t('testResults.scopeNoReferenceIndex')}</p>
        ) : null}
        {report.agents.map((group) => (
          <AgentGroup
            key={group.agent_id}
            group={group}
            canRate={canRate}
            formatTime={(iso) => dateTime.format(new Date(iso))}
            userLabel={userLabel}
            reporterLabel={reporterLabel}
            onRate={rate}
          />
        ))}
      </div>
    )
  }

  return (
    <section
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3"
      data-testid="test-results-panel"
      aria-busy={loading || undefined}
    >
      <div className="min-w-0 space-y-1">
        <h4
          id={headingId}
          ref={headingRef}
          tabIndex={-1}
          className="text-sm font-semibold outline-none"
        >
          {t('testResults.title')}
        </h4>
        {report !== null && error === null ? (
          <>
            <p className="text-sm text-muted-foreground">
              {report.affected_agent_count > 0
                ? t('testResults.affected', { count: report.affected_agent_count })
                : t('testResults.affectedNone')}
            </p>
            {total > 0 ? (
              // Wird angesagt, wenn ein nachtraeglicher Lauf die Zahlen aendert.
              <p aria-live="polite" className="text-sm font-medium" data-testid="test-results-summary">
                {summaryText(t, tally)}
              </p>
            ) : null}
          </>
        ) : null}
        {report !== null && total > 0 && onJumpToDiff !== undefined ? (
          <Button
            type="button"
            variant="link"
            size="sm"
            className="h-auto min-h-10 px-0 lg:hidden"
            onClick={onJumpToDiff}
          >
            {t('testResults.jumpToDiff')}
          </Button>
        ) : null}
      </div>
      {body}
    </section>
  )
}

type TFunction = ReturnType<typeof useTranslation>['t']

function summaryText(t: TFunction, tally: Record<TestResultKind, number>): string {
  const parts = [t('testResults.summary.passed', { count: tally.pass })]
  const failed = tally.fail + tally.error
  if (failed > 0) parts.push(t('testResults.summary.failed', { count: failed }))
  if (tally.missing > 0) parts.push(t('testResults.summary.missing', { count: tally.missing }))
  if (tally.awaiting > 0) parts.push(t('testResults.summary.awaiting', { count: tally.awaiting }))
  return parts.join(' · ')
}

function NoRunsYet({
  entityType,
  entityId,
  versionId,
  version,
}: {
  entityType: VersionedEntityType
  entityId: string
  versionId: string
  version: number
}) {
  const { t } = useTranslation('learning')
  const prompt = t('testResults.noRuns.prompt', {
    type: t(`testCases.entityType.${entityType}`),
    entityId,
    version,
    versionId,
    entityType,
  })
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm">{t('testResults.noRuns.title')}</p>
      <pre className="rounded-md border bg-muted/40 p-3 text-xs break-words whitespace-pre-wrap">
        {prompt}
      </pre>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="min-h-10 self-start md:min-h-0"
        onClick={() => {
          void copyToClipboard(prompt)
            .then(() => notify.success(t('testResults.noRuns.copied')))
            .catch((cause: unknown) =>
              notify.error(cause instanceof Error ? cause.message : t('common:errors.unknown')),
            )
        }}
      >
        <Copy aria-hidden="true" />
        {t('testResults.noRuns.copy')}
      </Button>
    </div>
  )
}

interface AgentGroupProps {
  group: TestReportAgentGroup
  canRate: boolean
  formatTime: (iso: string) => string
  userLabel: (userId: string | null) => string
  reporterLabel: (result: TestRunRead) => string | null
  onRate: (entry: TestReportEntry, verdict: TestVerdict) => Promise<void>
}

function AgentGroup({ group, canRate, formatTime, userLabel, reporterLabel, onRate }: AgentGroupProps) {
  const { t } = useTranslation('learning')
  const [showPassed, setShowPassed] = useState(false)
  const sorted = useMemo(
    () =>
      [...group.entries].sort(
        (a, b) =>
          KIND_ORDER[resultKind(a)] - KIND_ORDER[resultKind(b)] ||
          a.test_case.title.localeCompare(b.test_case.title),
      ),
    [group.entries],
  )
  const passed = sorted.filter((entry) => resultKind(entry) === 'pass')
  const collapse = passed.length >= COLLAPSE_PASSED_FROM && !showPassed
  const visible = collapse ? sorted.filter((entry) => resultKind(entry) !== 'pass') : sorted
  const name = group.agent_name || group.agent_id.slice(0, 8)
  const via = group.via.map((way) => t(`testResults.via.${way}`, { defaultValue: way })).join(', ')

  return (
    <section aria-label={t('testCases.group.agent', { name })} className="flex min-w-0 flex-col gap-2">
      <div className="min-w-0">
        <h5 className="text-sm font-medium break-words">{t('testCases.group.agent', { name })}</h5>
        {via ? (
          <p className="text-xs break-words text-muted-foreground">{t('testResults.viaLabel', { via })}</p>
        ) : null}
      </div>
      {sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('testResults.agentWithoutCases')}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {visible.map((entry) => (
            <ResultRow
              key={entry.test_case.id}
              entry={entry}
              canRate={canRate}
              formatTime={formatTime}
              userLabel={userLabel}
              reporterLabel={reporterLabel}
              onRate={onRate}
            />
          ))}
          {collapse ? (
            <li className="p-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="min-h-10 w-full justify-start md:min-h-0"
                aria-expanded={false}
                onClick={() => setShowPassed(true)}
              >
                <CheckCircle2 className="text-[var(--status-active)]" aria-hidden="true" />
                {t('testResults.morePassed', { count: passed.length })}
              </Button>
            </li>
          ) : null}
        </ul>
      )}
    </section>
  )
}

interface ResultRowProps {
  entry: TestReportEntry
  canRate: boolean
  formatTime: (iso: string) => string
  userLabel: (userId: string | null) => string
  reporterLabel: (result: TestRunRead) => string | null
  onRate: (entry: TestReportEntry, verdict: TestVerdict) => Promise<void>
}

function ResultRow({ entry, canRate, formatTime, userLabel, reporterLabel, onRate }: ResultRowProps) {
  const { t } = useTranslation('learning')
  const detailsId = useId()
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState<TestVerdict | null>(null)
  const kind = resultKind(entry)
  const Icon = KIND_ICON[kind]
  const { test_case: testCase, result } = entry
  const runs = result !== null ? `${result.runs_passed}/${result.runs_total}` : null
  // „Nicht bestanden · 1/3“: die Laufzahl steht immer neben dem Wort, damit
  // sichtbar ist, dass nur n/n als bestanden gilt.
  const word = t(`testResults.kind.${kind}`)

  const submitRating = async (verdict: TestVerdict) => {
    setRating(verdict)
    try {
      await onRate(entry, verdict)
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('testResults.rate.error'))
    } finally {
      setRating(null)
    }
  }

  let attestation: string | null = null
  // Kopfzeile: wer hat gemeldet (Agent bzw. Person), mit welchem Modell.
  let reporter: string | null = null
  if (result !== null) {
    const model = [result.model_provider, result.model_name].filter(Boolean).join(' / ')
    attestation =
      result.attestation === 'human_rating'
        ? t('testResults.attestation.human', {
            name: userLabel(result.reported_by_user_id),
            time: formatTime(result.created_at),
          })
        : t('testResults.attestation.client', {
            model: model || t('testResults.attestation.unknownModel'),
            time: formatTime(result.created_at),
          })
    const name = reporterLabel(result)
    if (name === null) {
      reporter = model
        ? t('testResults.reporter.unknownWithModel', { model })
        : t('testResults.reporter.unknown')
    } else if (result.attestation === 'human_rating') {
      reporter = t('testResults.reporter.human', { name })
    } else {
      reporter = model
        ? t('testResults.reporter.clientWithModel', { name, model })
        : t('testResults.reporter.client', { name })
    }
  }

  return (
    <li className="min-w-0" data-testid="test-result-row" data-kind={kind}>
      <Button
        type="button"
        variant="ghost"
        className="h-auto min-h-10 w-full min-w-0 items-start justify-start gap-2 rounded-none p-3 text-left font-normal whitespace-normal"
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={() => setOpen((prev) => !prev)}
      >
        <Icon className={cn('mt-0.5 size-4 shrink-0', KIND_ICON_CLASS[kind])} aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium break-words">{testCase.title}</span>
          <span className={cn('block text-xs', KIND_WORD_CLASS[kind])}>
            {word}
            {runs !== null ? ` · ${runs}` : ''}
            {entry.direct ? ` · ${t('testResults.direct')}` : ''}
          </span>
          {reporter !== null ? (
            <span className="block text-xs break-words text-muted-foreground" data-testid="test-result-reporter">
              {reporter}
            </span>
          ) : null}
        </span>
        <ChevronRight
          className={cn('mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-90')}
          aria-hidden="true"
        />
      </Button>
      {open ? (
        <div id={detailsId} className="flex min-w-0 flex-col gap-2 px-3 pb-3 text-sm">
          <Detail label={t('testResults.detail.input')} text={testCase.input} />
          <Detail label={t('testResults.detail.expected')} text={testCase.expected_behavior} />
          {result?.output_excerpt ? (
            <Detail label={t('testResults.detail.output')} text={result.output_excerpt} />
          ) : null}
          {attestation !== null ? (
            <p className="text-xs break-words text-muted-foreground">{attestation}</p>
          ) : (
            <p className="text-xs text-muted-foreground">{t('testResults.detail.noRun')}</p>
          )}
          {canRate && testCase.check_kind === 'human_rule' ? (
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t('testResults.rate.label', { title: testCase.title })}>
              <span className="text-xs text-muted-foreground">{t('testResults.rate.prompt')}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-h-10 md:min-h-0"
                disabled={rating !== null}
                aria-busy={rating === 'pass' || undefined}
                onClick={() => void submitRating('pass')}
              >
                {t('testResults.rate.pass')}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-h-10 md:min-h-0"
                disabled={rating !== null}
                aria-busy={rating === 'fail' || undefined}
                onClick={() => void submitRating('fail')}
              >
                {t('testResults.rate.fail')}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}

function Detail({ label, text }: { label: string; text: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <ExpandableText text={text} lines={4} className="text-sm break-words whitespace-pre-wrap" />
    </div>
  )
}
