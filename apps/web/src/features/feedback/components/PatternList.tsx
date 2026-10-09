import type { TFunction } from 'i18next'
import { Copy, Lightbulb, MessageSquareWarning } from 'lucide-react'
import {
  type RefObject,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type { Agent, CaseTarget, PatternListRead, PatternRead } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { CaseFromOriginDialog, ReportCaseDialog } from '@/components/cases/ReportCaseForm'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { MetaPill } from '@/components/data/MetaPill'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

// Belege im Sheet: die ersten 20, dann „Alle n Belege anzeigen“ (Spec S5).
const EVIDENCE_PAGE = 20
// Hit-Target der Aktionen: 44 px unter `md` (Mobil-Spec), 36 px darueber.
const ACTION = 'min-h-11 md:min-h-9'

type NamedTarget = 'persona' | 'playbook' | 'resource' | 'external_tool' | 'system_prompt_template'
const NAMED_TARGETS: ReadonlySet<CaseTarget> = new Set<CaseTarget>([
  'persona',
  'playbook',
  'resource',
  'external_tool',
  'system_prompt_template',
])

/**
 * Schluessel eines Musters fuer `?pattern=`. Muster haben keine ID (ADR 3.7),
 * der Schluessel steht fuer ihre Bedingung: Fall-Muster nach Agent und
 * Zuordnung, Lernvorschlag-Muster nach Agent und kleinster Beleg-ID (der
 * Server sortiert die Belege aufsteigend).
 */
function patternKey(pattern: PatternRead): string {
  if (pattern.source === 'case') {
    const element = pattern.element
    return `case.${pattern.agent_id}.${element?.target ?? '-'}.${element?.entity_id ?? '-'}`
  }
  return `lesson.${pattern.agent_id}.${pattern.evidence_ids[0] ?? '-'}`
}

/** Fälle vor Lernvorschlägen, darin Zähler absteigend; sonst Server-Reihenfolge. */
function sortPatterns(patterns: readonly PatternRead[]): PatternRead[] {
  const rank = (pattern: PatternRead) => (pattern.source === 'case' ? 0 : 1)
  return [...patterns].sort((a, b) => rank(a) - rank(b) || b.count - a.count)
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

const dateOf = (iso: string) => new Date(iso).toLocaleDateString()

interface PatternData {
  data: PatternListRead | null
  agents: Agent[]
  /** Elementnamen je `<target>:<entity_id>`; fehlt der Name, steht nur die Art. */
  names: Record<string, string>
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * `GET /patterns?agent_id` plus Agenten und Elementnamen. Ein Nachladen
 * behaelt die alte Antwort sichtbar, bis die neue da ist — so faellt ein
 * verschwundenes Muster erst mit der neuen Antwort weg.
 */
function usePatterns(agentId: string): PatternData {
  const api = useApi()
  const [data, setData] = useState<PatternListRead | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [names, setNames] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const generation = useRef(0)

  useEffect(() => {
    const current = ++generation.current
    setError(null)
    api
      .listPatterns(agentId === '' ? undefined : agentId)
      .then((result) => {
        if (current === generation.current) setData(result)
      })
      .catch((cause: unknown) => {
        if (current === generation.current) setError(messageOf(cause))
      })
      .finally(() => {
        if (current === generation.current) setLoading(false)
      })
  }, [api, agentId, nonce])

  useEffect(() => {
    let cancelled = false
    api
      .listAgents()
      .then((list) => {
        if (!cancelled) setAgents(list)
      })
      .catch(() => {
        if (!cancelled) setAgents([])
      })
    return () => {
      cancelled = true
    }
  }, [api])

  // Namen der zugeordneten Elemente. Gedaechtnis, Werkzeugrechte und
  // Modellgrenze erscheinen nur als Art (wie im Fall-Detail).
  useEffect(() => {
    if (data === null) return
    let cancelled = false
    const wanted = new Map<string, { target: NamedTarget; id: string }>()
    for (const pattern of data.patterns) {
      const element = pattern.element
      if (element?.entity_id && NAMED_TARGETS.has(element.target)) {
        wanted.set(`${element.target}:${element.entity_id}`, {
          target: element.target as NamedTarget,
          id: element.entity_id,
        })
      }
    }
    const fetchName = (target: NamedTarget, id: string): Promise<string> => {
      switch (target) {
        case 'persona':
          return api.getPersona(id).then((entity) => entity.name)
        case 'playbook':
          return api.getPlaybook(id).then((entity) => entity.name)
        case 'resource':
          return api.getResource(id).then((entity) => entity.name)
        case 'external_tool':
          return api.getExternalTool(id).then((entity) => entity.name)
        case 'system_prompt_template':
          return api.getSystemPromptTemplate(id).then((entity) => entity.name)
      }
    }
    const jobs = [...wanted.entries()].map(([key, { target, id }]) =>
      fetchName(target, id).then(
        (name) => [key, name] as const,
        () => null,
      ),
    )
    void Promise.all(jobs).then((results) => {
      if (cancelled) return
      const next: Record<string, string> = {}
      for (const entry of results) if (entry !== null) next[entry[0]] = entry[1]
      setNames(next)
    })
    return () => {
      cancelled = true
    }
  }, [api, data])

  const reload = useCallback(() => setNonce((value) => value + 1), [])
  return { data, agents, names, loading, error, reload }
}

/**
 * Leer ohne Filter: gibt es ueberhaupt Faelle oder Lernvorschlaege? Nur dann
 * gefragt, sonst bleibt es beim Spec-Text mit Schwelle. Scheitert eine Zahl,
 * gilt die Datenbasis als vorhanden (kein falscher „Es gibt noch keine“-Satz).
 */
function useHasBasis(enabled: boolean): boolean | null {
  const api = useApi()
  const [basis, setBasis] = useState<boolean | null>(null)
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    Promise.all([api.countCases(), api.countMemories({ kind: 'lesson' })])
      .then(([cases, lessons]) => {
        const caseTotal = Object.values(cases).reduce((sum, value) => sum + value, 0)
        if (!cancelled) setBasis(caseTotal > 0 || lessons.total > 0)
      })
      .catch(() => {
        if (!cancelled) setBasis(true)
      })
    return () => {
      cancelled = true
    }
  }, [api, enabled])
  return enabled ? basis : null
}

interface Texts {
  agentName: (id: string) => string
  elementLabel: (pattern: PatternRead) => string
}

function useTexts(agents: Agent[], names: Record<string, string>): Texts {
  const { t } = useTranslation(['feedback', 'learning'])
  return {
    agentName: (id) =>
      agents.find((agent) => agent.id === id)?.name ?? t('learning:approval.unknownAgent'),
    elementLabel: (pattern) => {
      const element = pattern.element
      if (element === null) return ''
      const kind = t(`feedback:cases.target.${element.target}`)
      const name = element.entity_id ? names[`${element.target}:${element.entity_id}`] : undefined
      return name !== undefined ? `${kind}: ${name}` : kind
    },
  }
}

function patternTitle(t: TFunction, pattern: PatternRead): string {
  return t(`feedback:patterns.kind.${pattern.source}.title`, { count: pattern.count })
}

function patternText(t: TFunction, pattern: PatternRead, texts: Texts, days: number): string {
  return pattern.source === 'case'
    ? t('feedback:patterns.kind.case.text', {
        count: pattern.count,
        agent: texts.agentName(pattern.agent_id),
        element: texts.elementLabel(pattern),
        days,
      })
    : t('feedback:patterns.kind.lesson.text', {
        count: pattern.count,
        agent: texts.agentName(pattern.agent_id),
      })
}

function dateRange(pattern: PatternRead): string {
  const first = dateOf(pattern.first_seen)
  const last = dateOf(pattern.last_seen)
  return first === last ? last : `${first} – ${last}`
}

/**
 * Erklaersatz mit der Schwelle aus der Antwort (Q8). Fehlt sie, steht der
 * Satz ohne Zahl da — die UI kodiert n nicht fest.
 */
function hasThreshold(data: PatternListRead | null): data is PatternListRead {
  return data !== null && Number.isFinite(data.threshold)
}

function thresholdText(t: TFunction, data: PatternListRead | null): string {
  return hasThreshold(data)
    ? t('feedback:patterns.description', { threshold: data.threshold })
    : t('feedback:patterns.descriptionNoThreshold')
}

// --- Belege -------------------------------------------------------------

type Evidence = { text: string; date: string } | 'deleted' | 'failed'

/** Laedt die sichtbaren Belege einzeln (`GET /memories/{id}` bzw. `GET /cases/{id}`). */
function useEvidence(pattern: PatternRead, ids: readonly string[]) {
  const api = useApi()
  const [items, setItems] = useState<Record<string, Evidence>>({})
  const key = ids.join(',')
  useEffect(() => {
    let cancelled = false
    const load = (id: string): Promise<Evidence> =>
      (pattern.source === 'lesson'
        ? api.getMemory(id).then((memory) => ({ text: memory.fact, date: memory.created_at }))
        : api.getCase(id).then((detail) => ({
            text: detail.case.expected_behavior,
            date: detail.case.created_at,
          }))
      ).catch((cause: unknown) =>
        cause instanceof ApiError && cause.status === 404 ? 'deleted' : 'failed',
      )
    const ids = key.split(',').filter(Boolean)
    void Promise.all(ids.map((id) => load(id).then((value) => [id, value] as const))).then(
      (entries) => {
        if (!cancelled) setItems(Object.fromEntries(entries))
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, pattern.source, key])
  return items
}

function EvidenceList({ pattern }: { pattern: PatternRead }) {
  const { t } = useTranslation(['feedback', 'common'])
  const wsPath = useWorkspacePath()
  const [showAll, setShowAll] = useState(false)
  const ids = showAll ? pattern.evidence_ids : pattern.evidence_ids.slice(0, EVIDENCE_PAGE)
  const items = useEvidence(pattern, ids)

  return (
    <section className="flex flex-col gap-3" aria-labelledby="pattern-evidence-heading">
      <h3 id="pattern-evidence-heading" className="text-sm font-semibold">
        {t('feedback:patterns.detail.evidence')}
      </h3>
      <ol className="flex flex-col divide-y rounded-lg border" data-testid="pattern-evidence">
        {ids.map((id) => {
          const item = items[id]
          let content
          if (item === undefined) {
            content = <Skeleton className="h-5 w-full" />
          } else if (item === 'deleted') {
            content = (
              <span className="text-sm text-muted-foreground">
                {t('feedback:patterns.detail.deleted')}
              </span>
            )
          } else if (item === 'failed') {
            content = (
              <span className="text-sm text-muted-foreground">{t('common:error.generic')}</span>
            )
          } else {
            const href =
              pattern.source === 'lesson'
                ? wsPath(`/memory?entry=${encodeURIComponent(id)}`)
                : wsPath(`/feedback/cases/${encodeURIComponent(id)}`)
            content = (
              <span className="flex min-w-0 flex-col gap-0.5">
                <Link
                  to={href}
                  className="line-clamp-2 rounded-sm text-sm wrap-anywhere text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {item.text}
                </Link>
                <time dateTime={item.date} className="text-xs text-muted-foreground">
                  {dateOf(item.date)}
                </time>
              </span>
            )
          }
          return (
            <li key={id} className="min-w-0 px-3 py-2">
              {content}
            </li>
          )
        })}
      </ol>
      {!showAll && pattern.evidence_ids.length > EVIDENCE_PAGE ? (
        <Button
          type="button"
          variant="outline"
          className={cn(ACTION, 'self-start')}
          onClick={() => setShowAll(true)}
        >
          {t('feedback:patterns.detail.showAll', { count: pattern.evidence_ids.length })}
        </Button>
      ) : null}
    </section>
  )
}

// --- Sheet --------------------------------------------------------------

interface PatternSheetProps {
  pattern: PatternRead | null
  data: PatternListRead | null
  texts: Texts
  onClose: () => void
  onConverted: () => void
}

/** Neuester geladener Lernvorschlag des Clusters: Zitat und Ziel von convert. */
function useNewestLesson(pattern: PatternRead) {
  const api = useApi()
  const [newest, setNewest] = useState<{ id: string; fact: string; date: string } | null>(null)
  const key = pattern.source === 'lesson' ? pattern.evidence_ids.join(',') : ''
  useEffect(() => {
    if (key === '') return
    let cancelled = false
    void Promise.all(
      key.split(',').map((id) =>
        api.getMemory(id).then(
          (memory) => memory,
          () => null,
        ),
      ),
    ).then((memories) => {
      if (cancelled) return
      const pending = memories.filter((memory) => memory !== null && memory.status === 'pending')
      pending.sort((a, b) => (b?.created_at ?? '').localeCompare(a?.created_at ?? ''))
      const first = pending[0]
      setNewest(first ? { id: first.id, fact: first.fact, date: first.created_at } : null)
    })
    return () => {
      cancelled = true
    }
  }, [api, key])
  return newest
}

function BuilderCopy({ prompt }: { prompt: string }) {
  const { t } = useTranslation(['feedback', 'common'])
  const id = useId()
  return (
    <div className="flex min-w-0 flex-col gap-2" data-testid="pattern-builder">
      <Label htmlFor={id}>{t('feedback:patterns.builder.label')}</Label>
      {/* Feste Hoehe wie `McpConfigCopy`: ein Schnipsel zum Kopieren. */}
      <Textarea
        id={id}
        readOnly
        autoGrow={false}
        rows={3}
        value={prompt}
        className="font-mono text-xs break-words"
        onFocus={(event) => event.currentTarget.select()}
      />
      <Button
        type="button"
        variant="outline"
        className={cn(ACTION, 'w-full sm:w-auto sm:self-start')}
        onClick={() => {
          void copyToClipboard(prompt).catch((cause: unknown) => {
            notify.error(cause instanceof Error ? cause.message : t('common:error.generic'))
          })
        }}
      >
        <Copy aria-hidden="true" />
        {t('feedback:patterns.builder.copy')}
      </Button>
    </div>
  )
}

function PatternDetail({
  pattern,
  data,
  texts,
  titleRef,
  onConverted,
}: {
  pattern: PatternRead
  data: PatternListRead
  texts: Texts
  titleRef: RefObject<HTMLHeadingElement>
  onConverted: () => void
}) {
  const { t } = useTranslation(['feedback'])
  const wsPath = useWorkspacePath()
  const newest = useNewestLesson(pattern)
  const agentName = texts.agentName(pattern.agent_id)

  // Kopierblock nur mit IDs, nie mit Inhalten: Fall-Texte koennen
  // personenbezogene Daten enthalten (Spec S5, Datenschutz).
  const element = pattern.element
  const elementRef =
    element === null
      ? ''
      : element.entity_id
        ? `${t(`feedback:cases.target.${element.target}`)} ${element.entity_id}`
        : t(`feedback:cases.target.${element.target}`)
  const prompt =
    pattern.source === 'lesson'
      ? t('feedback:patterns.builder.promptLesson', {
          id: newest?.id ?? pattern.evidence_ids[0] ?? '',
          agent: agentName,
        })
      : t('feedback:patterns.builder.promptCase', {
          ids: pattern.evidence_ids.join(', '),
          agent: agentName,
          element: elementRef,
        })

  const casesLink = useMemo(() => {
    const query = new URLSearchParams({ tab: 'cases', agent: pattern.agent_id })
    if (element !== null) query.set('target', element.target)
    return wsPath(`/feedback?${query.toString()}`)
  }, [wsPath, pattern.agent_id, element])

  return (
    <>
      <SheetHeader className="sticky top-0 z-10 gap-2 border-b bg-background p-4 pr-12 text-left">
        <SheetTitle ref={titleRef} tabIndex={-1} className="outline-none">
          {patternTitle(t, pattern)}
        </SheetTitle>
        <SheetDescription className="break-words">
          {agentName} · {dateRange(pattern)}
        </SheetDescription>
      </SheetHeader>

      <div className="flex min-w-0 flex-1 flex-col gap-6 p-4">
        <section className="flex flex-col gap-2" aria-labelledby="pattern-why-heading">
          <h3 id="pattern-why-heading" className="text-sm font-semibold">
            {t('feedback:patterns.detail.why')}
          </h3>
          <p className="text-sm break-words">{patternText(t, pattern, texts, data.window_days)}</p>
          <p className="text-sm text-muted-foreground">{thresholdText(t, data)}</p>
        </section>

        <EvidenceList key={patternKey(pattern)} pattern={pattern} />

        <BuilderCopy prompt={prompt} />
      </div>

      {/* Fixierte Aktionsleiste (Spec S5, 390 px). */}
      <div className="sticky bottom-0 flex flex-col gap-2 border-t bg-background p-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:flex-row">
        {pattern.source === 'lesson' ? (
          <CaseFromOriginDialog
            agent={{ id: pattern.agent_id, name: agentName }}
            origin={{
              kind: 'lesson',
              memoryId: newest?.id ?? '',
              agentName,
              count: pattern.count,
              text: newest?.fact ?? '',
              date: newest?.date ?? pattern.last_seen,
            }}
            label={t('feedback:patterns.action.createCase')}
            variant="brand"
            className={cn(ACTION, 'w-full sm:w-auto')}
            disabled={newest === null}
            onCreated={onConverted}
          />
        ) : (
          <Button asChild variant="brand" className={cn(ACTION, 'w-full sm:w-auto')}>
            <Link to={casesLink}>
              <MessageSquareWarning aria-hidden="true" />
              {t('feedback:patterns.action.viewCases')}
            </Link>
          </Button>
        )}
      </div>
    </>
  )
}

function PatternSheet({ pattern, data, texts, onClose, onConverted }: PatternSheetProps) {
  const mobile = useIsMobile()
  const titleRef = useRef<HTMLHeadingElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const open = pattern !== null && data !== null

  // Ausloeser merken (Zeilen-Link), bevor Radix den Fokus ins Sheet holt.
  useLayoutEffect(() => {
    if (!open) return
    const active = document.activeElement
    returnFocus.current = active instanceof HTMLElement && active !== document.body ? active : null
  }, [open])

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent
        side={mobile ? 'bottom' : 'right'}
        data-testid="pattern-sheet"
        className={cn(
          // Der Schliessen-Knopf von `SheetContent` liegt absolut und muss
          // ueber dem fixierten Kopf (`z-10`) bleiben.
          'gap-0 overflow-x-hidden overflow-y-auto overscroll-contain p-0 [&>button]:z-20',
          mobile ? 'h-[100svh] rounded-none' : 'w-full sm:max-w-lg',
        )}
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          titleRef.current?.focus()
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          const target = returnFocus.current
          if (target !== null && target.isConnected) target.focus()
        }}
      >
        {open ? (
          <PatternDetail
            key={patternKey(pattern)}
            pattern={pattern}
            data={data}
            texts={texts}
            titleRef={titleRef}
            onConverted={onConverted}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

// --- Liste --------------------------------------------------------------

function PatternRow({
  pattern,
  data,
  texts,
  href,
}: {
  pattern: PatternRead
  data: PatternListRead
  texts: Texts
  href: string
}) {
  const { t } = useTranslation(['feedback'])
  return (
    <EntityCard
      icon={pattern.source === 'case' ? MessageSquareWarning : Lightbulb}
      iconTone="catalog"
      title={patternTitle(t, pattern)}
      href={href}
      description={patternText(t, pattern, texts, data.window_days)}
      meta={<MetaPill>{dateRange(pattern)}</MetaPill>}
    />
  )
}

function PatternSkeletons() {
  const { t } = useTranslation('data')
  return (
    <div className="flex flex-col gap-3" aria-live="polite" aria-busy="true">
      <span className="sr-only">{t('loading')}</span>
      {[0, 1].map((index) => (
        <Skeleton key={index} className="h-24 w-full rounded-xl" data-testid="pattern-skeleton" />
      ))}
    </div>
  )
}

/**
 * Tab „Muster“ im Feedback-Hub (Delta-Spec S5, ADR-0053 3.7; nur editor).
 * Muster sind berechnet und haben keinen Zustand: kein Status, kein
 * Verwerfen, keine Kennung. Die Liste zeigt Zaehlung und Belege und deutet
 * nichts. Filter nur Agent (`?agent=`), Detail als Sheet (`?pattern=`).
 */
export function PatternList() {
  const { t } = useTranslation(['feedback', 'data', 'common'])
  const [params, setParams] = useSearchParams()
  const agent = params.get('agent') ?? ''
  const openKey = params.get('pattern')
  const { data, agents, names, loading, error, reload } = usePatterns(agent)
  const texts = useTexts(agents, names)

  const patterns = useMemo(() => sortPatterns(data?.patterns ?? []), [data])
  const openPattern =
    openKey === null ? null : (patterns.find((pattern) => patternKey(pattern) === openKey) ?? null)

  const update = useCallback(
    (change: (next: URLSearchParams) => void) =>
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          change(next)
          return next
        },
        { replace: true },
      ),
    [setParams],
  )

  // Beim Oeffnen neu berechnen lassen: verschwindet das Muster inzwischen,
  // meldet das die naechste Antwort.
  const previousKey = useRef(openKey)
  useEffect(() => {
    if (openKey !== null && previousKey.current !== openKey) reload()
    previousKey.current = openKey
  }, [openKey, reload])

  // Muster weg (abgelehnt, umgewandelt, eingeordnet, aus dem Fenster) oder
  // toter Deep-Link: Toast und Sheet zu (Spec S5 „Muster verschwunden“).
  useEffect(() => {
    if (openKey === null || data === null || openPattern !== null) return
    notify.info(t('feedback:patterns.gone'))
    update((next) => next.delete('pattern'))
  }, [openKey, data, openPattern, t, update])

  const closeSheet = () => update((next) => next.delete('pattern'))
  // Nach convert faellt das Muster weg: erst schliessen, dann neu laden —
  // so meldet das Sheet nicht „gilt nicht mehr“ fuer die eigene Aktion.
  const onConverted = () => {
    closeSheet()
    reload()
  }

  const rowHref = (pattern: PatternRead) => {
    const next = new URLSearchParams(params)
    next.set('pattern', patternKey(pattern))
    return `?${next.toString()}`
  }

  const active = agent !== ''
  const reset = () => update((next) => next.delete('agent'))
  const emptyUnfiltered = data !== null && patterns.length === 0 && !active
  const basis = useHasBasis(emptyUnfiltered)

  const description = thresholdText(t, data)

  let body
  if (loading && data === null) {
    body = <PatternSkeletons />
  } else if (error !== null && data === null) {
    body = (
      <div className="flex flex-col items-start gap-3">
        <ErrorAlert title={t('feedback:patterns.loadError')} message={error} />
        <Button type="button" variant="outline" onClick={reload}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  } else if (data !== null && patterns.length === 0) {
    body = active ? (
      <EmptyState
        title={t('data:filter.emptyFilteredTitle')}
        action={
          <Button type="button" variant="outline" onClick={reset}>
            {t('data:filter.reset')}
          </Button>
        }
      />
    ) : basis === false ? (
      <EmptyState
        title={t('feedback:patterns.emptyNoData')}
        action={<ReportCaseDialog variant="brand" />}
      />
    ) : (
      <EmptyState
        title={t('feedback:patterns.emptyTitle')}
        description={
          hasThreshold(data)
            ? t('feedback:patterns.emptyDescription', { threshold: data.threshold })
            : undefined
        }
      />
    )
  } else if (data !== null) {
    body = (
      <ul className="flex flex-col gap-3" data-testid="pattern-list">
        {patterns.map((pattern) => (
          <li key={patternKey(pattern)}>
            <PatternRow pattern={pattern} data={data} texts={texts} href={rowHref(pattern)} />
          </li>
        ))}
      </ul>
    )
  }

  const agentOptions = [...agents]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((entry) => ({ id: entry.id, name: entry.name }))

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm text-muted-foreground">{description}</p>
        <p className="text-sm text-muted-foreground">{t('feedback:patterns.vanishHint')}</p>
      </div>
      {emptyUnfiltered ? null : (
        <ListFilterBar
          agents={agentOptions}
          agent={agent}
          onAgentChange={(value) =>
            update((next) => (value === '' ? next.delete('agent') : next.set('agent', value)))
          }
          active={active}
          onReset={reset}
          idPrefix="patterns-filter"
        />
      )}
      {error !== null && data !== null ? (
        <ErrorAlert title={t('feedback:patterns.loadError')} message={error} />
      ) : null}
      {body}
      <PatternSheet
        pattern={openPattern}
        data={data}
        texts={texts}
        onClose={closeSheet}
        onConverted={onConverted}
      />
    </section>
  )
}
