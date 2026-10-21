import { CalendarClock } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Api } from '@/api/client'
import type { Dossier, DossierGeneration, DossierMeasure } from '@/api/types'
import { useApi } from '@/api/useApi'
import { MetaPill } from '@/components/data/MetaPill'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { followUpStatusOf, formatDay, isDue } from '@/features/evolution/lib/followUp'
import { cn } from '@/lib/utils'

// Verlauf (Generationen) im Agent-Tab „Weiterentwicklung“ (Neuschnitt §3.6,
// Paket E5k, Weiche N2 a). Datenquelle ist der Dossier-Block `generations`
// (E1): je Aktivierung eines Bausteins ein Eintrag, neueste zuerst.
//
// Eine Quelle je Ansicht (PM 2026-10-14): Reihenfolge, Versionen, Einstufung,
// verknuepfte Aenderungen (`measure_ids`, leer = direkt geaendert) und
// „betrifft auch“ kommen vom Server. Die Ansicht sortiert nicht, verknuepft
// nicht ueber Baustein-IDs und leitet keinen Zustand aus Events ab. Lokal
// bleibt nur der Kalendertag „faellig?“ einer offenen Aenderung
// (`followUpStatusOf`, wie Tab und Review-Ergebnis).
//
// Grenze: Beim Oeffnen genau eine Anfrage `getDossier(agentId)`; der Server
// liefert hoechstens `DOSSIER_GENERATIONS_LIMIT` (15) Generationen je Seite.
// Sichtbar sind zuerst 5, „Aeltere Generationen zeigen“ deckt 10 weitere auf
// und laedt erst dann die naechste Seite (`generations_next_cursor`), wenn die
// geladenen aufgebraucht sind. Keine Anfrage je Generation (kein N+1).
//
// IDs: Ein Link auf eine Aenderung entsteht nur, wenn der Server sie im
// Dossier DIESES Agenten mitliefert und `id` und `session_id` UUIDs sind.
// Ein Dossier mit fremder `agent_id` wird verworfen.

/** Zuerst sichtbare Generationen (§3.6). */
export const TIMELINE_INITIAL = 5
/** Weitere je Klick auf „Aeltere Generationen zeigen“ (§3.6). */
export const TIMELINE_STEP = 10

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

interface TimelineState {
  status: 'loading' | 'ok' | 'error'
  items: DossierGeneration[]
  /** Aenderungen aus den geladenen Dossier-Seiten, nach `id`. */
  measures: Record<string, DossierMeasure>
  nextCursor: string | null
  loadingMore: boolean
  moreFailed: boolean
}

const INITIAL: TimelineState = {
  status: 'loading',
  items: [],
  measures: {},
  nextCursor: null,
  loadingMore: false,
  moreFailed: false,
}

function measuresById(dossier: Dossier): Record<string, DossierMeasure> {
  const byId: Record<string, DossierMeasure> = {}
  for (const measure of Array.isArray(dossier.measures) ? dossier.measures : []) {
    if (UUID.test(measure.id) && UUID.test(measure.session_id)) byId[measure.id] = measure
  }
  return byId
}

/** Dossier nur fuer genau diesen Agenten; alles andere ist ein Fehler. */
function loadPage(api: Api, agentId: string, cursor?: string): Promise<Dossier> {
  return Promise.resolve()
    .then(() => api.getDossier(agentId, cursor !== undefined ? { cursor } : undefined))
    .then((dossier) => {
      if (dossier.agent_id !== agentId || !Array.isArray(dossier.generations)) {
        throw new Error('dossier_mismatch')
      }
      return dossier
    })
}

function useGenerations(agentId: string) {
  const api = useApi()
  // Der Zustand gehoert zu Client und Agent; bei einem Wechsel gilt er als
  // „laden“, ohne ihn im Effect synchron zurueckzusetzen.
  const [stored, setStored] = useState<{ api: Api; agentId: string; value: TimelineState } | null>(
    null,
  )
  const state = stored !== null && stored.api === api && stored.agentId === agentId ? stored.value : INITIAL
  const setState = useCallback(
    (update: (prev: TimelineState) => TimelineState) =>
      setStored((prev) => ({
        api,
        agentId,
        value: update(prev !== null && prev.api === api && prev.agentId === agentId ? prev.value : INITIAL),
      })),
    [api, agentId],
  )

  useEffect(() => {
    let alive = true
    loadPage(api, agentId).then(
      (dossier) => {
        if (!alive) return
        setState(() => ({
          status: 'ok',
          items: dossier.generations,
          measures: measuresById(dossier),
          nextCursor: dossier.generations_next_cursor,
          loadingMore: false,
          moreFailed: false,
        }))
      },
      () => {
        if (alive) setState(() => ({ ...INITIAL, status: 'error' }))
      },
    )
    return () => {
      alive = false
    }
  }, [api, agentId, setState])

  // Eine Seite, die nach einem Agentwechsel ankommt, wird verworfen.
  const current = useRef({ api, agentId })
  useEffect(() => {
    current.current = { api, agentId }
  }, [api, agentId])

  const loadMore = useCallback(() => {
    const cursor = state.nextCursor
    if (cursor === null || state.loadingMore) return
    const stillCurrent = () => current.current.api === api && current.current.agentId === agentId
    setState((prev) => ({ ...prev, loadingMore: true, moreFailed: false }))
    loadPage(api, agentId, cursor).then(
      (dossier) => {
        if (!stillCurrent()) return
        setState((prev) => ({
          ...prev,
          items: [...prev.items, ...dossier.generations],
          measures: { ...prev.measures, ...measuresById(dossier) },
          nextCursor: dossier.generations_next_cursor,
          loadingMore: false,
        }))
      },
      () => {
        if (stillCurrent()) setState((prev) => ({ ...prev, loadingMore: false, moreFailed: true }))
      },
    )
  }, [api, agentId, state.nextCursor, state.loadingMore, setState])

  return { ...state, loadMore }
}

interface EvolutionTimelineProps {
  agentId: string
  /** Link auf das Review-Ergebnis mit geoeffneter Aenderung. */
  changeHref: (sessionId: string, measureId: string) => string
  /** Datum der geladenen Reviews (`id` → `created_at`), fuer „Review vom …“. */
  reviewDates: Record<string, string>
}

export function EvolutionTimeline({ agentId, changeHref, reviewDates }: EvolutionTimelineProps) {
  const { t } = useTranslation('sessions')
  const data = useGenerations(agentId)
  // Sichtbare Anzahl je Agent: ein neuer Agent beginnt wieder bei 5.
  const [shownFor, setShownFor] = useState({ agentId, count: TIMELINE_INITIAL })
  const visible = shownFor.agentId === agentId ? shownFor.count : TIMELINE_INITIAL

  const shown = data.items.slice(0, visible)
  const hiddenLoaded = data.items.length > visible
  const canShowMore = hiddenLoaded || data.nextCursor !== null

  const showMore = () => {
    const target = visible + TIMELINE_STEP
    setShownFor({ agentId, count: target })
    if (data.items.length < target && data.nextCursor !== null) data.loadMore()
  }

  return (
    <section
      className="flex min-w-0 flex-col gap-3"
      aria-labelledby="evolution-timeline-title"
      data-testid="evolution-timeline"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <h2 id="evolution-timeline-title" className="text-lg font-semibold">
          {t('evolution.timeline.title')}
        </h2>
        <p className="text-sm break-words text-muted-foreground">{t('evolution.timeline.intro')}</p>
      </div>
      {data.status === 'loading' ? (
        <div aria-busy="true" className="flex flex-col gap-2" data-testid="evolution-timeline-loading">
          <Skeleton className="h-14 w-full rounded-xl" />
          <Skeleton className="h-14 w-full rounded-xl" />
        </div>
      ) : data.status === 'error' ? (
        <p className="text-sm text-muted-foreground" role="alert">
          {t('evolution.timeline.loadError')}
        </p>
      ) : data.items.length === 0 ? (
        <p
          className="rounded-xl border border-dashed bg-muted/30 p-4 text-sm break-words"
          data-testid="evolution-timeline-empty"
        >
          {t('evolution.timeline.empty')}
        </p>
      ) : (
        <>
          <ol className="flex min-w-0 flex-col" aria-label={t('evolution.timeline.listAria')}>
            {shown.map((generation, index) => (
              <GenerationItem
                key={`${generation.entity_type}:${generation.entity_id}:${generation.activated_at}:${index}`}
                generation={generation}
                measures={data.measures}
                reviewDates={reviewDates}
                changeHref={changeHref}
                last={index === shown.length - 1}
              />
            ))}
          </ol>
          {data.moreFailed ? (
            <p className="text-sm text-muted-foreground" role="alert">
              {t('evolution.timeline.moreError')}
            </p>
          ) : null}
          {canShowMore ? (
            <div>
              <Button
                type="button"
                variant="ghost"
                className="min-h-11 md:min-h-10"
                disabled={data.loadingMore}
                onClick={showMore}
              >
                {t('evolution.timeline.more')}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}

/** Erste vom Server mitgelieferte Aenderung dieser Aktivierung. */
function linkedMeasure(
  generation: DossierGeneration,
  measures: Record<string, DossierMeasure>,
): DossierMeasure | undefined {
  for (const id of generation.measure_ids) {
    const measure = measures[id]
    if (measure !== undefined) return measure
  }
  return undefined
}

function GenerationItem({
  generation,
  measures,
  reviewDates,
  changeHref,
  last,
}: {
  generation: DossierGeneration
  measures: Record<string, DossierMeasure>
  reviewDates: Record<string, string>
  changeHref: (sessionId: string, measureId: string) => string
  last: boolean
}) {
  const { t } = useTranslation(['sessions', 'feedback'])
  const direct = generation.measure_ids.length === 0
  const measure = direct ? undefined : linkedMeasure(generation, measures)
  const kind = t(`feedback:cases.target.${generation.entity_type}`)
  const versions =
    generation.from_version !== null
      ? t('evolution.timeline.versions', { from: generation.from_version, to: generation.to_version })
      : t('evolution.timeline.firstVersion', { to: generation.to_version })
  const element = `${kind} ${generation.name}`

  // Ergebnis-Pill: Einstufung vom Server; ohne Einstufung der Termin der
  // verknuepften Aenderung (Server-Zustand und -Datum, lokal nur „faellig?“).
  let pill: { text: string; due: boolean } | null = null
  if (direct) {
    pill = { text: t('evolution.timeline.direct'), due: false }
  } else if (generation.verdict !== null) {
    pill = { text: t(`measure.state.${generation.verdict}`), due: false }
  } else if (measure !== undefined) {
    const status = followUpStatusOf(measure, { follow_up_at: measure.follow_up_at })
    if (status.kind === 'closed') pill = { text: t(`measure.state.${status.state}`), due: false }
    else if (isDue(status)) pill = { text: t('measure.due'), due: true }
    else pill = { text: t('measure.followUpOn', { date: formatDay(status.date) }), due: false }
  }

  const parts: string[] = []
  if (direct) {
    parts.push(t('evolution.timeline.noFollowUp'))
  } else if (measure !== undefined) {
    const reviewDate = reviewDates[measure.session_id]
    parts.push(
      reviewDate !== undefined
        ? t('evolution.timeline.whyReview', {
            count: measure.case_count,
            date: formatDay(reviewDate),
          })
        : t('evolution.timeline.why', { count: measure.case_count }),
    )
  } else {
    parts.push(t('evolution.timeline.fromReview'))
  }
  if (generation.shared_agent_count !== null && generation.shared_agent_count > 0) {
    parts.push(t('evolution.timeline.shared', { count: generation.shared_agent_count }))
  }

  return (
    <li className="relative flex min-w-0 gap-3 pb-4" data-testid="evolution-generation">
      <div className="flex shrink-0 flex-col items-center pt-1" aria-hidden="true">
        <span
          className={cn(
            'size-3 rounded-full border-2',
            direct ? 'border-dashed border-muted-foreground bg-background' : 'border-foreground bg-foreground',
          )}
          data-testid={direct ? 'evolution-generation-dot-direct' : 'evolution-generation-dot'}
        />
        {!last ? <span className="mt-1 w-px flex-1 bg-border" /> : null}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span className="min-w-0 font-medium break-words" data-testid="evolution-generation-title">
            <time dateTime={generation.activated_at.slice(0, 10)}>
              {t('evolution.timeline.generation', { date: formatDay(generation.activated_at) })}
            </time>
            {' · '}
            {element} {versions}
          </span>
          {pill !== null ? (
            <MetaPill
              tone={pill.due ? 'brand' : 'muted'}
              icon={pill.due ? CalendarClock : undefined}
              className="whitespace-normal"
            >
              <span data-testid="evolution-generation-result">{pill.text}</span>
            </MetaPill>
          ) : null}
        </p>
        <p className="text-xs break-words text-muted-foreground" data-testid="evolution-generation-meta">
          {parts.join(' · ')}
        </p>
        {measure !== undefined ? (
          <div>
            <Link
              to={changeHref(measure.session_id, measure.id)}
              className="inline-flex min-h-11 items-center text-xs font-medium underline-offset-4 hover:underline md:min-h-9"
              aria-label={t('evolution.timeline.openAria', { element })}
            >
              {t('evolution.timeline.open')}
            </Link>
          </div>
        ) : null}
      </div>
    </li>
  )
}
