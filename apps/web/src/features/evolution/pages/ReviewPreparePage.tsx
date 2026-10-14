import { ClipboardCopy, MessagesSquare } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type {
  Agent,
  CaseRead,
  CaseSeverity,
  CaseStatus,
  Dossier,
  DossierElement,
  DossierVersion,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DetailHeader } from '@/components/data'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { BuilderPromptCopy } from '@/features/evolution/components/BuilderPromptCopy'
import { formatDay } from '@/features/evolution/lib/followUp'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { copyToClipboard } from '@/lib/clipboard'
import { uiLocale } from '@/lib/dates'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

// Review vorbereiten (Neuschnitt §2, §4; E5-Delta §3, Inhalte). Code-Namen
// bleiben bei der API (Case = Rueckmeldung, Session = Review, Dossier = Lage),
// die Texte folgen A4a.
//
// Die Seite speichert nichts (E5-Delta §0.1). Sie buendelt ① Rueckmeldungen
// auswaehlen, ② die Lage lesen (Dossier, nur lesend) und ③ den Startsatz fuer
// den Client kopieren. Die Auswahl steht in `?cases=` (nur UUIDs), damit Fall-
// Detail und Aenderung vorbelegen koennen.
//
// Rechte (E5-Delta §0.3): ab editor. Ein viewer wird per `replace` auf den
// Tab „Weiterentwicklung“ geleitet; fuer ihn geht kein einziger Request raus.
// Solange die Rolle unbekannt ist, wird nichts geladen.
//
// Eine Quelle je Wert (PM 2026-10-14): Zaehler, Raten-Rohzahlen und
// „zu wenig Nutzung“ kommen aus `GET /agents/{id}/dossier`. Die UI rechnet nur
// „je 100“ (QE8 a) und zaehlt nichts aus der Auswahl-Liste nach. Die Lage ist
// genau ein Request; die Seite laedt je Element nichts nach (kein N+1), Namen
// frueherer Aenderungen kommen aus den Bausteinen derselben Antwort.
//
// Datenschutz (D-Delta S5): Der Kopiertext enthaelt nur Agent-Name/-ID,
// Rueckmeldungs-UUIDs und Werkzeugnamen, nie Inhalte aus Rueckmeldungen oder
// der Lage.

/** Rueckmeldungen je Seite der Auswahl (E5-Delta §3: „die ersten 20“). */
export const PREPARE_CASES_PAGE = 20
/** Fruehere Aenderungen in der Lage (E5-Delta §3: „Höchstens 5“). */
export const PREPARE_MEASURES_SHOWN = 5
/** Ab so vielen gewaehlten Rueckmeldungen erscheint der Hinweis (kein Verbot). */
export const PREPARE_TOO_MANY = 4

// Status der Auswahl (E5-Delta §3): `in_progress` hat schon eine Aenderung.
const SELECTABLE: readonly CaseStatus[] = ['triaged', 'open', 'reopened']
const SEVERITY_RANK: Record<CaseSeverity, number> = { high: 0, medium: 1, low: 2 }
// Offene Status der Lage in fester Reihenfolge; nur, was der Server liefert.
const OPEN_ORDER: readonly CaseStatus[] = ['open', 'reopened', 'triaged', 'in_progress']
// Status-Chip der Fall-Liste je Status (`open` deckt `reopened` mit ab).
const CHIP_OF: Partial<Record<CaseStatus, string>> = {
  open: 'open',
  reopened: 'open',
  triaged: 'triaged',
  in_progress: 'in_progress',
}
// Hoechstens so viele IDs aus der URL (Schutz gegen ueberlange Links).
const MAX_SELECTED = 50
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
// Hoehe der fixierten Leiste unter `md` plus Luft (E5-Delta §8).
const STICKY_SCROLL_PADDING = 'calc(var(--cookie-banner-height, 0px) + 6rem)'
const LINK_MARK = '[[link]]'

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

/** `?cases=` als Liste eindeutiger UUIDs; alles andere faellt weg. */
function parseCaseIds(raw: string | null): string[] {
  if (raw === null) return []
  const seen = new Set<string>()
  for (const part of raw.split(',')) {
    const id = part.trim().toLowerCase()
    if (UUID.test(id)) seen.add(id)
    if (seen.size >= MAX_SELECTED) break
  }
  return [...seen]
}

/** Schwere absteigend, dann neueste zuerst. */
function bySeverityThenDate(a: CaseRead, b: CaseRead): number {
  const rank = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]
  if (rank !== 0) return rank
  return b.created_at.localeCompare(a.created_at)
}

// ------------------------------------------------------------------ Daten

interface AgentState {
  agent: Agent | null
  notFound: boolean
  error: string | null
}

function useAgent(agentId: string, enabled: boolean): AgentState & { reload: () => void } {
  const api = useApi()
  const [state, setState] = useState<AgentState>({ agent: null, notFound: false, error: null })
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api.getAgent(agentId).then(
      (agent) => {
        if (!cancelled) setState({ agent, notFound: false, error: null })
      },
      (cause: unknown) => {
        if (cancelled) return
        if (cause instanceof ApiError && cause.status === 404) {
          setState({ agent: null, notFound: true, error: null })
        } else {
          setState({ agent: null, notFound: false, error: messageOf(cause) })
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, agentId, enabled, nonce])
  const reload = useCallback(() => {
    setState({ agent: null, notFound: false, error: null })
    setNonce((value) => value + 1)
  }, [])
  return { ...state, reload }
}

interface CasesState {
  items: CaseRead[] | null
  nextCursor: string | null
  loadingMore: boolean
  error: string | null
  loadMore: () => void
}

function useSelectableCases(agentId: string, enabled: boolean): CasesState {
  const api = useApi()
  const [items, setItems] = useState<CaseRead[] | null>(null)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api.listCases({ agent_id: agentId, status: SELECTABLE }, { limit: PREPARE_CASES_PAGE }).then(
      (page) => {
        if (cancelled) return
        setItems(page.items)
        setNextCursor(page.next_cursor)
      },
      (cause: unknown) => {
        if (!cancelled) setError(messageOf(cause))
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, agentId, enabled])

  const loadMore = useCallback(() => {
    // Gesperrt waehrend des Ladens: ein Doppelklick loest keinen zweiten Request aus.
    if (nextCursor === null || loadingMore) return
    setLoadingMore(true)
    api
      .listCases(
        { agent_id: agentId, status: SELECTABLE },
        { cursor: nextCursor, limit: PREPARE_CASES_PAGE },
      )
      .then(
        (page) => {
          setItems((current) => {
            const known = new Set((current ?? []).map((item) => item.id))
            return [...(current ?? []), ...page.items.filter((item) => !known.has(item.id))]
          })
          setNextCursor(page.next_cursor)
        },
        (cause: unknown) => notify.error(messageOf(cause)),
      )
      .finally(() => setLoadingMore(false))
  }, [api, agentId, nextCursor, loadingMore])

  return { items, nextCursor, loadingMore, error, loadMore }
}

interface DossierState {
  dossier: Dossier | null
  loading: boolean
  error: string | null
  reload: () => void
}

function useDossier(agentId: string, enabled: boolean): DossierState {
  const api = useApi()
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api
      .getDossier(agentId)
      .then(
        (loaded) => {
          if (!cancelled) setDossier(loaded)
        },
        (cause: unknown) => {
          if (!cancelled) setError(messageOf(cause))
        },
      )
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, agentId, enabled, nonce])
  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    setNonce((value) => value + 1)
  }, [])
  return { dossier, loading, error, reload }
}

// ------------------------------------------------------------------ Bausteine

function Step({
  title,
  testId,
  children,
}: {
  title: string
  testId: string
  children: ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-col gap-3" data-testid={testId}>
      <h2 className="text-lg font-semibold break-words">{title}</h2>
      {children}
    </section>
  )
}

function NoData() {
  const { t } = useTranslation('sessions')
  return (
    <p className="text-sm text-muted-foreground" data-testid="situation-no-data">
      {t('prepare.situation.noData')}
    </p>
  )
}

/**
 * Eine Karte der Lage: ab `md` Karte mit `h3`, darunter Akkordeon
 * (`details`, E5-Delta §3 „390 px“; „Offene Rückmeldungen“ offen).
 */
function SituationCard({
  title,
  testId,
  mobile,
  defaultOpen,
  wide = false,
  children,
}: {
  title: string
  testId: string
  mobile: boolean
  defaultOpen: boolean
  wide?: boolean
  children: ReactNode
}) {
  if (mobile) {
    return (
      <details
        className="group min-w-0 rounded-xl border bg-card p-4 shadow-card"
        open={defaultOpen}
        data-testid={testId}
      >
        <summary className="flex min-h-11 cursor-pointer items-center">
          <h3 className="text-sm font-semibold break-words">{title}</h3>
        </summary>
        <div className="mt-3 min-w-0">{children}</div>
      </details>
    )
  }
  return (
    <section
      className={cn(
        'flex min-w-0 flex-col gap-3 rounded-xl border bg-card p-4 shadow-card',
        // Die Raten-Tabelle braucht die volle Breite (sechs Spalten).
        wide && 'md:col-span-2',
      )}
      data-testid={testId}
    >
      <h3 className="text-sm font-semibold break-words">{title}</h3>
      {children}
    </section>
  )
}

// ------------------------------------------------------------------ Lage

interface RateRow {
  key: string
  element: DossierElement
  version: DossierVersion
}

function signalText(signals: Record<string, number>, label: (key: string) => string): string {
  const parts = Object.entries(signals)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => `${label(key)} ${count}`)
  return parts.length === 0 ? '–' : parts.join(' · ')
}

function Situation({
  dossier,
  agentId,
  agentName,
  mobile,
}: {
  dossier: Dossier
  agentId: string
  agentName: string
  mobile: boolean
}) {
  const { t } = useTranslation(['sessions', 'feedback'])
  const wsPath = useWorkspacePath()
  const integer = new Intl.NumberFormat(uiLocale())
  const decimal = new Intl.NumberFormat(uiLocale(), {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })

  // ---- Offene Rueckmeldungen: Zaehler wie geliefert.
  const counts = OPEN_ORDER.filter((status) => dossier.open_cases.counts[status] !== undefined)
  const caseListHref = (status: CaseStatus) => {
    const params = new URLSearchParams({ tab: 'cases', agent: agentId })
    const chip = CHIP_OF[status]
    if (chip !== undefined) params.set('status', chip)
    return wsPath(`/feedback?${params.toString()}`)
  }

  // ---- Rate je Version.
  const rows: RateRow[] = dossier.elements.flatMap((element) =>
    element.versions.map((version) => ({
      key: `${element.entity_type}:${element.entity_id}:${version.version}`,
      element,
      version,
    })),
  )
  const withSignals = rows.some((row) => Object.values(row.version.signals).some((n) => n > 0))
  const signalLabel = (key: string) =>
    t(`feedback:signal.${key}`, { defaultValue: key })
  const elementLabel = (element: DossierElement) =>
    `${t(`feedback:cases.target.${element.entity_type}`)} „${element.name}“`
  const rate = (version: DossierVersion): string => {
    if (version.insufficient) return t('prepare.situation.tooFewUses')
    if (version.cases === null || version.uses <= 0) return '–'
    return decimal.format((version.cases * 100) / version.uses)
  }
  const versionText = (version: DossierVersion) =>
    version.active
      ? t('prepare.situation.versionActive', { version: version.version })
      : t('prepare.situation.version', { version: version.version })
  const casesText = (version: DossierVersion) =>
    version.cases === null ? '–' : integer.format(version.cases)

  // ---- Fruehere Aenderungen: Namen aus den Bausteinen derselben Antwort.
  const nameOf = new Map(dossier.elements.map((element) => [element.entity_id, element.name]))
  const measures = dossier.measures.slice(0, PREPARE_MEASURES_SHOWN)
  const measureElement = (target: string, entityId: string | null) => {
    const kind = t(`feedback:cases.target.${target}`)
    const name = entityId !== null ? nameOf.get(entityId) : undefined
    return name !== undefined ? `${kind} „${name}“` : kind
  }

  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 md:grid-cols-2" data-testid="situation">
      <SituationCard
        title={t('prepare.situation.openCases')}
        testId="situation-open-cases"
        mobile={mobile}
        defaultOpen
      >
        {counts.length === 0 ? (
          <NoData />
        ) : (
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 text-sm">
            {counts.map((status) => (
              <div key={status} className="contents" data-testid={`situation-count-${status}`}>
                <dt className="min-w-0 break-words">
                  <Link to={caseListHref(status)} className="text-brand hover:underline">
                    {t(`feedback:cases.status.${status}`)}
                  </Link>
                </dt>
                <dd className="text-right tabular-nums">
                  {integer.format(dossier.open_cases.counts[status] ?? 0)}
                </dd>
              </div>
            ))}
            <dt className="border-t pt-1 font-medium">{t('prepare.situation.total')}</dt>
            <dd
              className="border-t pt-1 text-right font-medium tabular-nums"
              data-testid="situation-total"
            >
              {integer.format(dossier.open_cases.total)}
            </dd>
          </dl>
        )}
      </SituationCard>

      <SituationCard
        title={t('prepare.situation.access')}
        testId="situation-access"
        mobile={mobile}
        defaultOpen={false}
      >
        {dossier.access.total === 0 && dossier.access.rows.length === 0 ? (
          <NoData />
        ) : (
          <dl className="grid grid-cols-1 gap-x-3 gap-y-1 text-sm sm:grid-cols-[auto_minmax(0,1fr)]">
            <dt className="text-muted-foreground">{t('prepare.situation.accessWindow')}</dt>
            <dd className="min-w-0 break-words">
              {t('prepare.situation.accessWindowValue', {
                days: dossier.access.window_days,
                date: formatDay(dossier.access.since),
              })}
            </dd>
            <dt className="text-muted-foreground">{t('prepare.situation.accessTotal')}</dt>
            <dd className="tabular-nums">{integer.format(dossier.access.total)}</dd>
            {dossier.access.rows.map((row) => (
              <div
                key={`${row.ref_kind}:${row.operation}:${row.sensitivity}`}
                className="contents"
                data-testid="access-row"
              >
                <dt className="font-mono text-xs break-words text-muted-foreground">
                  {row.ref_kind} · {row.operation} · {row.sensitivity}
                </dt>
                <dd className="min-w-0 break-words">
                  {t('prepare.situation.accessRow', {
                    entries: integer.format(row.entries),
                    refs: integer.format(row.refs),
                    date: formatDay(row.last_on),
                  })}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </SituationCard>

      <SituationCard
        title={t('prepare.situation.rates')}
        testId="situation-rates"
        mobile={mobile}
        wide
        defaultOpen={false}
      >
        {rows.length === 0 ? (
          <NoData />
        ) : (
          <>
            {/* Ab md eine echte Tabelle, darunter Karten mit Labels (E5-Delta §8). */}
            <table className="hidden w-full text-sm md:table" data-testid="situation-rate-table">
              <caption className="sr-only">{t('prepare.situation.rates')}</caption>
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pr-2 font-medium">
                    {t('prepare.situation.col.element')}
                  </th>
                  <th scope="col" className="py-2 pr-2 font-medium">
                    {t('prepare.situation.col.version')}
                  </th>
                  <th scope="col" className="py-2 pr-2 text-right font-medium">
                    {t('prepare.situation.col.cases')}
                  </th>
                  <th scope="col" className="py-2 pr-2 text-right font-medium">
                    {t('prepare.situation.col.uses')}
                  </th>
                  <th scope="col" className="py-2 pr-2 text-right font-medium">
                    {t('prepare.situation.col.rate')}
                  </th>
                  {withSignals ? (
                    <th scope="col" className="py-2 font-medium">
                      {t('prepare.situation.col.signals')}
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key} className="border-b last:border-b-0" data-testid="rate-row">
                    <th scope="row" className="py-2 pr-2 text-left align-top font-medium break-words">
                      {elementLabel(row.element)}
                    </th>
                    <td className="py-2 pr-2 align-top">{versionText(row.version)}</td>
                    <td className="py-2 pr-2 text-right align-top tabular-nums">
                      {casesText(row.version)}
                    </td>
                    <td className="py-2 pr-2 text-right align-top tabular-nums">
                      {integer.format(row.version.uses)}
                    </td>
                    <td className="py-2 pr-2 text-right align-top tabular-nums" data-testid="rate-value">
                      {rate(row.version)}
                    </td>
                    {withSignals ? (
                      <td className="py-2 align-top break-words">
                        {signalText(row.version.signals, signalLabel)}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="flex flex-col gap-2 md:hidden" data-testid="situation-rate-cards">
              {rows.map((row) => (
                <li key={row.key} className="min-w-0 rounded-lg border p-3">
                  <p className="text-sm font-medium break-words">
                    {elementLabel(row.element)} · {versionText(row.version)}
                  </p>
                  <dl className="mt-1 grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 text-sm">
                    <dt className="text-muted-foreground">{t('prepare.situation.col.cases')}</dt>
                    <dd className="text-right tabular-nums">{casesText(row.version)}</dd>
                    <dt className="text-muted-foreground">{t('prepare.situation.col.uses')}</dt>
                    <dd className="text-right tabular-nums">{integer.format(row.version.uses)}</dd>
                    <dt className="text-muted-foreground">{t('prepare.situation.col.rate')}</dt>
                    <dd className="text-right tabular-nums">{rate(row.version)}</dd>
                    {withSignals ? (
                      <>
                        <dt className="text-muted-foreground">{t('prepare.situation.col.signals')}</dt>
                        <dd className="min-w-0 text-right break-words">
                          {signalText(row.version.signals, signalLabel)}
                        </dd>
                      </>
                    ) : null}
                  </dl>
                </li>
              ))}
            </ul>
            {dossier.elements_total > dossier.elements.length ? (
              <p className="text-xs text-muted-foreground" data-testid="situation-elements-more">
                {t('prepare.situation.elementsMore', {
                  shown: dossier.elements.length,
                  total: dossier.elements_total,
                })}
              </p>
            ) : null}
          </>
        )}
      </SituationCard>

      <SituationCard
        title={t('prepare.situation.pastMeasures')}
        testId="situation-measures"
        mobile={mobile}
        defaultOpen={false}
      >
        {measures.length === 0 ? (
          <NoData />
        ) : (
          <div className="flex min-w-0 flex-col gap-2">
            <ul className="flex flex-col gap-2">
              {measures.map((measure) => (
                <li key={measure.id} className="min-w-0 text-sm" data-testid="situation-measure">
                  <Link
                    to={wsPath(
                      `/agents/${encodeURIComponent(agentId)}/reviews/${encodeURIComponent(
                        measure.session_id,
                      )}?change=${encodeURIComponent(measure.id)}`,
                    )}
                    className="font-medium break-words text-brand hover:underline"
                  >
                    {measureElement(measure.target, measure.entity_id)}
                  </Link>
                  <span className="block text-xs text-muted-foreground">
                    <time dateTime={measure.created_at}>{formatDay(measure.created_at)}</time>
                    {' · '}
                    {t(`sessions:measure.state.${measure.state}`)}
                  </span>
                </li>
              ))}
            </ul>
            {dossier.measures_total > measures.length ? (
              <Link
                to={wsPath(`/agents/${encodeURIComponent(agentId)}?tab=evolution`)}
                className="text-sm font-medium text-brand hover:underline"
                data-testid="situation-all-reviews"
              >
                {t('prepare.situation.allReviews', { agent: agentName })}
              </Link>
            ) : null}
          </div>
        )}
      </SituationCard>
    </div>
  )
}

function SituationSkeleton() {
  const { t } = useTranslation('data')
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2" aria-busy="true">
      <span className="sr-only">{t('loading')}</span>
      {[0, 1, 2, 3].map((index) => (
        <Skeleton key={index} className="h-32 w-full rounded-xl" data-testid="situation-skeleton" />
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ Auswahl

function CaseOption({
  item,
  checked,
  onToggle,
}: {
  item: CaseRead
  checked: boolean
  onToggle: (id: string) => void
}) {
  const { t } = useTranslation('feedback')
  const id = `prepare-case-${item.id}`
  return (
    <li className="flex min-h-11 min-w-0 items-start gap-3 py-2" data-testid="prepare-case">
      <Checkbox
        id={id}
        className="mt-0.5"
        checked={checked}
        onChange={() => onToggle(item.id)}
        data-case-id={item.id}
      />
      <Label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer flex-col gap-0.5 font-normal">
        <span className="line-clamp-2 text-sm break-words">
          {t('cases.row.expected', { text: item.expected_behavior })}
        </span>
        <span className="text-xs text-muted-foreground">
          {t(`cases.status.${item.status}`)} · {t(`cases.report.severity.${item.severity}`)} ·{' '}
          <time dateTime={item.created_at}>{formatDay(item.created_at)}</time>
        </span>
      </Label>
    </li>
  )
}

// ------------------------------------------------------------------ Seite

/**
 * Review vorbereiten: `/w/:ws/agents/:agentId/reviews/prepare?cases=<id,…>`
 * (Neuschnitt §2, Weiche N4 a). Steht in `routes.tsx` vor `:sessionId`.
 */
export function ReviewPreparePage() {
  const { agentId } = useParams<{ agentId: string }>()
  // Frischer Zustand je Agent.
  return <ReviewPrepareView key={agentId} agentId={agentId ?? ''} />
}

function ReviewPrepareView({ agentId }: { agentId: string }) {
  const { t } = useTranslation(['sessions', 'feedback', 'common'])
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const isEditor = role === 'editor' || role === 'admin'
  const mobile = useIsMobile()
  const [params, setParams] = useSearchParams()
  const [copied, setCopied] = useState(false)

  const agentState = useAgent(agentId, isEditor)
  const cases = useSelectableCases(agentId, isEditor)
  const situation = useDossier(agentId, isEditor)

  // Auswaehlbar ist nur, was der Server fuer diesen Agenten mit auswaehlbarem
  // Status geliefert hat. IDs aus `?cases=`, die (noch) nicht in der Liste
  // stehen, zaehlen weder im Startsatz noch in Leiste oder Hinweis; ein
  // praeparierter Link schiebt so keine fremden IDs in den Builder-Auftrag.
  // Nachgeladen wird je ID nichts (kein N+1): steht sie auf einer spaeteren
  // Seite, wird sie mit „Weitere laden“ gueltig.
  const knownIds = useMemo(
    () =>
      new Set(
        (cases.items ?? [])
          .filter((item) => item.agent_id === agentId && SELECTABLE.includes(item.status))
          .map((item) => item.id.toLowerCase()),
      ),
    [cases.items, agentId],
  )
  const rawCases = params.get('cases')
  const requested = useMemo(() => parseCaseIds(rawCases), [rawCases])
  const selected = useMemo(() => requested.filter((id) => knownIds.has(id)), [requested, knownIds])
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const unresolved = cases.items === null ? 0 : requested.length - selected.length

  const toggle = useCallback(
    (id: string) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          // Unbekannte IDs fallen beim ersten Toggle aus der URL.
          const list = parseCaseIds(current.get('cases')).filter((item) => knownIds.has(item))
          const updated = list.includes(id) ? list.filter((item) => item !== id) : [...list, id]
          if (updated.length === 0) next.delete('cases')
          else next.set('cases', updated.join(','))
          return next
        },
        { replace: true },
      )
    },
    [setParams, knownIds],
  )

  // Fixierte Leiste unter md: der fokussierte Inhalt darf nicht darunter
  // liegen (E5-Delta §8). Der Scrollport ist das Wurzelelement (globals.css).
  useEffect(() => {
    if (!mobile || !isEditor) return
    const root = document.documentElement
    const previous = root.style.scrollPaddingBottom
    root.style.scrollPaddingBottom = STICKY_SCROLL_PADDING
    return () => {
      root.style.scrollPaddingBottom = previous
    }
  }, [mobile, isEditor])

  const evolutionHref = wsPath(`/agents/${encodeURIComponent(agentId)}?tab=evolution`)

  if (role === null) {
    return (
      <Container>
        <Skeleton className="h-10 w-2/3 max-w-sm" />
      </Container>
    )
  }
  if (!isEditor) return <Navigate to={evolutionHref} replace />

  if (agentState.notFound) {
    return (
      <Container>
        <EmptyState
          icon={MessagesSquare}
          title={t('feedback:cases.report.error.agentGone')}
          action={
            <Button asChild variant="outline">
              <Link to={wsPath('/agents')}>{t('feedback:cases.report.toAgents')}</Link>
            </Button>
          }
        />
      </Container>
    )
  }
  if (agentState.error !== null) {
    return (
      <Container>
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert message={agentState.error} />
          <Button type="button" variant="outline" onClick={agentState.reload}>
            {t('common:actions.retry')}
          </Button>
        </div>
      </Container>
    )
  }

  const agent = agentState.agent
  const agentName = agent?.name ?? ''

  // Nur Name, ID und UUIDs (D-Delta S5); live mit der Auswahl.
  const prompt =
    agent === null
      ? ''
      : [
          t('prepare.prompt', { agent: agent.name, agentId: agent.id }),
          selected.length > 0 ? t('prepare.promptCases', { ids: selected.join(', ') }) : null,
        ]
          .filter((part): part is string => part !== null)
          .join(' ')

  const items = cases.items ?? []
  const triaged = items.filter((item) => item.status === 'triaged').sort(bySeverityThenDate)
  const untriaged = items.filter((item) => item.status !== 'triaged').sort(bySeverityThenDate)

  const onStickyCopy = () => {
    void copyToClipboard(prompt)
      .then(() => {
        notify.success(t('sessions:copy.copied'))
        setCopied(true)
      })
      .catch((cause: unknown) => notify.error(messageOf(cause)))
  }

  // Satz mit eingebettetem Link ohne <Trans>: am Platzhalter teilen.
  const [linkBefore = '', linkAfter = ''] = t('prepare.afterCopy', { link: LINK_MARK }).split(LINK_MARK)

  return (
    <Container>
      <div className={cn('flex flex-col gap-8', mobile && 'pb-24')}>
        <DetailHeader
          icon={MessagesSquare}
          iconTone="catalog"
          title={t('prepare.title')}
          backHref={evolutionHref}
          backLabel={t('sessions:detail.back', { agent: agentName })}
          description={agentName}
        />

        <Step title={t('prepare.step.cases')} testId="prepare-step-cases">
          {cases.error !== null ? (
            <ErrorAlert message={cases.error} title={t('prepare.casesLoadError')} />
          ) : cases.items === null ? (
            <Skeleton className="h-24 w-full rounded-xl" />
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="prepare-no-cases">
              {t('prepare.noCases', { agent: agentName })}
            </p>
          ) : (
            <div className="flex min-w-0 flex-col gap-4">
              {triaged.length > 0 ? (
                <fieldset className="min-w-0" data-testid="prepare-group-triaged">
                  <legend className="text-sm font-semibold">{t('prepare.group.triaged')}</legend>
                  <ul className="mt-1 flex flex-col divide-y">
                    {triaged.map((item) => (
                      <CaseOption
                        key={item.id}
                        item={item}
                        checked={selectedSet.has(item.id)}
                        onToggle={toggle}
                      />
                    ))}
                  </ul>
                </fieldset>
              ) : null}
              {untriaged.length > 0 ? (
                <fieldset
                  className="min-w-0"
                  aria-describedby="prepare-untriaged-help"
                  data-testid="prepare-group-untriaged"
                >
                  <legend className="text-sm font-semibold">{t('prepare.group.untriaged')}</legend>
                  <p id="prepare-untriaged-help" className="text-xs text-muted-foreground">
                    {t('prepare.group.untriagedHelp')}
                  </p>
                  <ul className="mt-1 flex flex-col divide-y">
                    {untriaged.map((item) => (
                      <CaseOption
                        key={item.id}
                        item={item}
                        checked={selectedSet.has(item.id)}
                        onToggle={toggle}
                      />
                    ))}
                  </ul>
                </fieldset>
              ) : null}
              {cases.nextCursor !== null ? (
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11 self-start md:min-h-9"
                  aria-busy={cases.loadingMore}
                  disabled={cases.loadingMore}
                  onClick={cases.loadMore}
                  data-testid="prepare-load-more"
                >
                  {t('prepare.loadMore')}
                </Button>
              ) : null}
            </div>
          )}
          {unresolved > 0 ? (
            <p
              role="status"
              className="text-sm text-muted-foreground"
              data-testid="prepare-unresolved"
            >
              {t('prepare.unresolved', { count: unresolved })}
            </p>
          ) : null}
          {selected.length >= PREPARE_TOO_MANY ? (
            <p
              role="status"
              className="border-brand-border bg-brand-soft rounded-lg border px-3 py-2 text-sm"
              data-testid="prepare-too-many"
            >
              {t('prepare.tooMany')}
            </p>
          ) : null}
        </Step>

        <Step title={t('prepare.step.situation')} testId="prepare-step-situation">
          {situation.dossier !== null ? (
            <Situation
              dossier={situation.dossier}
              agentId={agentId}
              agentName={agentName}
              mobile={mobile}
            />
          ) : situation.error !== null ? (
            <div className="flex flex-col items-start gap-3" data-testid="situation-error">
              <ErrorAlert message={situation.error} title={t('prepare.situation.loadError')} />
              <Button
                type="button"
                variant="outline"
                disabled={situation.loading}
                onClick={situation.reload}
              >
                {t('common:actions.retry')}
              </Button>
            </div>
          ) : (
            <SituationSkeleton />
          )}
        </Step>

        <Step title={t('prepare.step.start')} testId="prepare-step-start">
          <p className="text-sm text-muted-foreground">{t('prepare.startIntro')}</p>
          {agent === null ? (
            <Skeleton className="h-28 w-full rounded-xl" />
          ) : (
            <BuilderPromptCopy
              prompt={prompt}
              variant="brand"
              onCopied={() => setCopied(true)}
              testId="prepare-copy"
            />
          )}
          {copied ? (
            <p className="text-sm break-words" data-testid="prepare-after-copy">
              {linkBefore}
              <Link to={evolutionHref} className="font-medium text-brand hover:underline">
                {t('prepare.afterCopyLink', { agent: agentName })}
              </Link>
              {linkAfter}
            </p>
          ) : null}
        </Step>
      </div>

      {mobile && agent !== null ? (
        <div
          role="region"
          aria-label={t('prepare.step.start')}
          className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-card"
          data-testid="prepare-sticky"
        >
          <Button
            type="button"
            variant="brand"
            className="min-h-11 w-full"
            onClick={onStickyCopy}
          >
            <ClipboardCopy aria-hidden="true" />
            {t('prepare.copySticky', { count: selected.length })}
          </Button>
        </div>
      ) : null}
    </Container>
  )
}
