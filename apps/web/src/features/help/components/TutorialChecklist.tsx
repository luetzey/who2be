import { CheckCircle2, ChevronDown, ChevronRight, Circle, CircleSlash } from 'lucide-react'
import { type ReactNode, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import type { Tutorial, TutorialStep, TutorialStepState } from '@/api/client'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  findTutorial,
  type HelpIndex,
  helpIndex as defaultIndex,
  type HelpTutorial,
  safeHelpHref,
  toHelpLocale,
} from '@/help/helpIndex'
import { notify } from '@/lib/feedback'
import { AGENT_CONNECT_HASH } from '@/lib/installLinks'
import { cn } from '@/lib/utils'

import {
  finishedSteps,
  readHelpNavigationState,
  stepsForRole,
  type TutorialsState,
  useTutorials,
} from '../hooks/useTutorials'
import { HelpMarkdown } from './HelpMarkdown'

/*
 * Startliste auf dem Dashboard (Onboarding P3, Spec §6.1).
 *
 * Generisch: gezeigt wird jedes Tutorial mit `welcome: true` (heute „Erste
 * Schritte“). Schritte, Typen und Zustaende kommen nur vom Server, Titel und
 * Text aus dem Markdown je Sprache — kein Schritt ist hier hart codiert.
 *
 * „Ausblenden“ hat in ADR-0060 keinen eigenen Speicherort: es setzt alle
 * offenen Schritte ueber das vorhandene PATCH auf „uebersprungen“ (PM W2 a).
 * Die Karte „Du bist startklar“ erscheint nur, wenn alle Schritte wirklich
 * erledigt sind, und nur bis 7 Tage nach dem letzten Haken.
 */

/** So lange bleibt „Du bist startklar“ stehen (Spec §6.1). */
const DONE_CARD_DAYS = 7
const DAY_MS = 24 * 60 * 60 * 1000

type ChecklistPhase = 'open' | 'done' | 'gone'

/**
 * Zustand der Karte aus den sichtbaren Schritten: `open`, solange ein Schritt
 * offen ist; `done` („Du bist startklar“), wenn alle erledigt sind und der
 * letzte Haken hoechstens {@link DONE_CARD_DAYS} Tage alt ist; sonst `gone`
 * (ausgeblendet, uebersprungen oder abgelaufen).
 */
function checklistPhase(steps: TutorialStep[], now: number): ChecklistPhase {
  if (steps.length === 0) return 'gone'
  if (steps.some((step) => step.state === 'open')) return 'open'
  if (!steps.every((step) => step.state === 'done')) return 'gone'
  const last = Math.max(
    ...steps.map((step) => (step.completed_at === null ? 0 : Date.parse(step.completed_at) || 0)),
  )
  if (last === 0) return 'gone'
  return now - last <= DONE_CARD_DAYS * DAY_MS ? 'done' : 'gone'
}

/** Fortschrittsbalken (geteilt mit der Hilfe-Seite). */
export function TutorialProgressBar({
  done,
  total,
  label,
}: {
  done: number
  total: number
  label: string
}) {
  const percent = total > 0 ? Math.round((done / total) * 100) : 0
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full bg-primary transition-[width] duration-[var(--duration-base)] ease-standard"
        style={{ width: `${percent}%` }}
        role="progressbar"
        aria-valuenow={done}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={label}
      />
    </div>
  )
}

function StepIcon({ state }: { state: TutorialStepState }) {
  if (state === 'done') {
    // Gleiche Farbe wie bestandene Pruefungen (TestResultsPanel).
    return <CheckCircle2 className="size-6 shrink-0 text-[var(--status-active)]" aria-hidden="true" />
  }
  if (state === 'skipped') {
    return <CircleSlash className="size-6 shrink-0 text-muted-foreground" aria-hidden="true" />
  }
  return <Circle className="size-6 shrink-0 text-muted-foreground" aria-hidden="true" />
}

/** Nur relative Ziele aus dem Katalog werden zu Links (keine ungepruefte URL). */
function stepPage(step: TutorialStep): string | null {
  if (step.page === null) return null
  const safe = safeHelpHref(step.page)
  return safe !== null && safe.startsWith('/') ? safe : null
}

/**
 * ID des mitgelieferten Builders (verwalteter Agent, `is_managed`) fuer den
 * Verbinden-Schritt (UX-Audit B1). Geladen wird nur, solange ein solcher
 * Schritt offen ist. `null` heisst: keiner da oder Laden gescheitert — dann
 * bleibt der Knopf beim Rueckfall auf die Agentenliste.
 */
function useBuilderId(enabled: boolean): string | null {
  const api = useApi()
  const [builderId, setBuilderId] = useState<string | null>(null)
  useEffect(() => {
    if (!enabled) return
    let alive = true
    api.listAgents().then(
      (agents) => {
        if (!alive) return
        // Ein aktiver Builder zuerst; sonst irgendein verwalteter Agent.
        const managed = agents.filter((agent) => agent.is_managed === true)
        const found = managed.find((agent) => agent.status === 'enabled') ?? managed[0]
        setBuilderId(found?.id ?? null)
      },
      () => {
        if (alive) setBuilderId(null)
      },
    )
    return () => {
      alive = false
    }
  }, [api, enabled])
  return enabled ? builderId : null
}

interface StepActionsProps {
  step: TutorialStep
  busy: boolean
  builderId: string | null
  onSet: (state: TutorialStepState) => void
}

function StepActions({ step, busy, builderId, onSet }: StepActionsProps) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  if (step.type === 'head_start') return null
  const actions: ReactNode[] = []
  const full = 'w-full sm:w-auto'
  if (step.state === 'open') {
    if (step.automatic) {
      // Verbinden-Schritt: ein Klick bis zur Karte „Verbindung“ des Builders
      // (Ueberblick, Anker `#connect`). Ohne Builder: die Agentenliste.
      const toBuilder = step.type === 'first_mcp_call' && builderId !== null
      actions.push(
        <Button key="agents" asChild size="sm" className={full}>
          {toBuilder ? (
            <Link to={wsPath(`/agents/${encodeURIComponent(builderId)}${AGENT_CONNECT_HASH}`)}>
              {t('checklist.connectBuilder')}
            </Link>
          ) : (
            <Link to={wsPath('/agents')}>{t('checklist.openAgents')}</Link>
          )}
        </Button>,
      )
    }
    const page = step.type === 'page_visited' ? stepPage(step) : null
    if (page !== null) {
      actions.push(
        <Button key="visit" asChild size="sm" className={full}>
          <Link to={wsPath(page)}>{t('tutorial.actions.openPage')}</Link>
        </Button>,
      )
    }
    if (step.type === 'manual') {
      actions.push(
        <Button key="done" size="sm" className={full} onClick={() => onSet('done')} disabled={busy}>
          {t('tutorial.actions.markDone')}
        </Button>,
      )
    }
    actions.push(
      <Button
        key="skip"
        variant="ghost"
        size="sm"
        className={full}
        onClick={() => onSet('skipped')}
        disabled={busy}
      >
        {t('tutorial.actions.skip')}
      </Button>,
    )
  } else if (step.state === 'skipped' || !step.automatic) {
    actions.push(
      <Button
        key="reopen"
        variant="ghost"
        size="sm"
        className={full}
        onClick={() => onSet('open')}
        disabled={busy}
      >
        {t('tutorial.actions.reopen')}
      </Button>,
    )
  }
  return (
    <div className="space-y-2">
      {step.automatic && step.state === 'open' ? (
        <p className="text-sm text-muted-foreground">{t('tutorial.automaticHint')}</p>
      ) : null}
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">{actions}</div>
    </div>
  )
}

interface StepRowProps {
  step: TutorialStep
  text: HelpTutorial
  next: boolean
  expanded: boolean
  busy: boolean
  builderId: string | null
  onToggle: () => void
  onSet: (state: TutorialStepState) => void
}

function StepRow({ step, text, next, expanded, busy, builderId, onToggle, onSet }: StepRowProps) {
  const { t } = useTranslation('help')
  const panelId = useId()
  const block = text.blocks.find((item) => item.id === step.id)
  const title = block?.title ?? step.id
  const stateLabel =
    step.state === 'done'
      ? t('checklist.state.done')
      : step.state === 'skipped'
        ? t('checklist.state.skipped')
        : next
          ? t('checklist.state.next')
          : null
  const Chevron = expanded ? ChevronDown : ChevronRight
  return (
    <li className={cn('border-t', next && 'bg-muted/30')}>
      <Button
        type="button"
        variant="ghost"
        className="h-auto min-h-11 w-full justify-start gap-3 rounded-none px-6 py-3 text-left text-base font-normal whitespace-normal hover:bg-muted/50 focus-visible:ring-offset-0 focus-visible:ring-inset [&_svg:first-child]:size-6"
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <StepIcon state={step.state} />
        <span
          className={cn(
            'min-w-0 flex-1 break-words',
            step.state === 'open' ? 'font-medium' : 'text-muted-foreground',
            step.state === 'done' && 'line-through',
          )}
        >
          {title}
          {stateLabel !== null ? (
            <>
              {' '}
              <span className="sr-only">({stateLabel})</span>
            </>
          ) : null}
        </span>
        <Chevron className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </Button>
      <div id={panelId} hidden={!expanded} className="space-y-3 px-6 pb-4 sm:pl-15">
        {block !== undefined ? <HelpMarkdown>{block.body}</HelpMarkdown> : null}
        <StepActions step={step} busy={busy} builderId={builderId} onSet={onSet} />
      </div>
    </li>
  )
}

interface ChecklistCardProps {
  tutorial: Tutorial
  text: HelpTutorial
  steps: TutorialStep[]
  state: TutorialsState
}

function OpenCard({ tutorial, text, steps, state }: ChecklistCardProps) {
  const { t } = useTranslation('help')
  const titleId = useId()
  const location = useLocation()
  const headingRef = useRef<HTMLHeadingElement>(null)
  const { pending, reload, setStep } = state
  const [choice, setChoice] = useState<{ id: string | null } | null>(null)
  const [hiding, setHiding] = useState(false)
  const [hideFailed, setHideFailed] = useState(false)
  const nextStep = steps.find((step) => step.state === 'open') ?? null
  // Ohne eigene Wahl ist der naechste offene Schritt aufgeklappt.
  const expandedId = choice === null ? (nextStep?.id ?? null) : choice.id
  const done = finishedSteps({ steps })
  const busy = pending !== null || hiding
  // Builder nur nachschlagen, solange der Verbinden-Schritt offen ist.
  const builderId = useBuilderId(
    steps.some((step) => step.type === 'first_mcp_call' && step.state === 'open'),
  )

  // Sprung aus dem „?“-Menue („Erste Schritte“): Fokus auf die Ueberschrift,
  // einmal je Navigation (`location.key`).
  const focusTarget = readHelpNavigationState(location.state).focusTutorial
  useEffect(() => {
    if (focusTarget !== tutorial.id) return
    headingRef.current?.focus()
    headingRef.current?.scrollIntoView?.({ block: 'start' })
  }, [location.key, focusTarget, tutorial.id])

  async function hide() {
    if (busy) return
    setHiding(true)
    setHideFailed(false)
    try {
      for (const step of steps) {
        if (step.state !== 'open') continue
        // Nacheinander: der Hook sperrt parallele Aenderungen ohnehin.
        const result = await setStep(tutorial.id, step.id, 'skipped')
        if (result === null) {
          setHideFailed(true)
          reload()
          return
        }
      }
      notify.info(t('checklist.hidden', { title: text.title }))
    } finally {
      setHiding(false)
    }
  }

  return (
    <Card aria-labelledby={titleId} role="region" data-testid={`tutorial-checklist-${tutorial.id}`}>
      <CardHeader className="gap-2 space-y-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <CardTitle
              id={titleId}
              ref={headingRef}
              tabIndex={-1}
              className="focus-visible:outline-none"
            >
              {text.title}
            </CardTitle>
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {t('checklist.progress', {
                done,
                total: steps.length,
                minutes: text.durationMinutes,
              })}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void hide()} disabled={busy}>
            {t('checklist.hide')}
          </Button>
        </div>
        <TutorialProgressBar
          done={done}
          total={steps.length}
          label={t('tutorial.progress.aria', { title: text.title })}
        />
        {hideFailed ? <ErrorAlert message={t('checklist.hideFailed')} /> : null}
      </CardHeader>
      <ol className="pb-2">
        {steps.map((step) => (
          <StepRow
            key={step.id}
            step={step}
            text={text}
            next={step.id === nextStep?.id}
            expanded={step.id === expandedId}
            busy={busy}
            builderId={builderId}
            onToggle={() => setChoice({ id: step.id === expandedId ? null : step.id })}
            onSet={(next) => void setStep(tutorial.id, step.id, next)}
          />
        ))}
      </ol>
    </Card>
  )
}

function DoneCard({ tutorial, text }: Pick<ChecklistCardProps, 'tutorial' | 'text'>) {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  const titleId = useId()
  return (
    <Card aria-labelledby={titleId} role="region" data-testid={`tutorial-checklist-${tutorial.id}`}>
      <CardContent className="flex flex-col gap-4 pt-6 sm:flex-row sm:items-center">
        <StepIcon state="done" />
        <div className="min-w-0 flex-1 space-y-1">
          <CardTitle id={titleId}>{t('checklist.done.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {t('checklist.done.body', { title: text.title })}
          </p>
        </div>
        <Button asChild variant="outline" className="w-full sm:w-auto">
          <Link to={wsPath('/help')}>{t('checklist.done.help')}</Link>
        </Button>
      </CardContent>
    </Card>
  )
}

function StatusCard({ children }: { children: ReactNode }) {
  const { t } = useTranslation('help')
  const titleId = useId()
  return (
    <Card aria-labelledby={titleId} role="region">
      <CardHeader>
        <CardTitle id={titleId}>{t('checklist.title')}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** Neu laden, wenn der Tab den Fokus zurueckbekommt (Rueckkehr aus Claude, O6). */
function useReloadOnReturn(reload: () => void) {
  useEffect(() => {
    function onVisible() {
      if (document.visibilityState === 'visible') reload()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [reload])
}

/**
 * Startliste fuer das Dashboard. `index` ist nur fuer Tests austauschbar;
 * `now` ebenso (Ablauf der Karte „Du bist startklar“).
 */
export function TutorialChecklist({
  index = defaultIndex,
  now,
}: {
  index?: HelpIndex
  now?: number
}) {
  const { t, i18n } = useTranslation('help')
  const locale = toHelpLocale(i18n.resolvedLanguage ?? i18n.language)
  const role = useCurrentWorkspaceRole()
  const state = useTutorials()
  const { tutorials, loading, error, reload } = state
  useReloadOnReturn(reload)
  // Sprung aus dem „?“-Menue, waehrend das Dashboard schon offen ist (z. B.
  // nach „Einführung erneut starten“): die Liste ist dann veraltet. Beim
  // ersten Rendern laedt der Hook ohnehin, deshalb erst ab der naechsten
  // Navigation.
  const location = useLocation()
  const [mountKey] = useState(location.key)
  const jump = readHelpNavigationState(location.state)
  const jumped = jump.focusTutorial !== undefined || jump.replayWelcome === true
  useEffect(() => {
    if (jumped && location.key !== mountKey) reload()
  }, [jumped, location.key, mountKey, reload])
  // Zeitpunkt einmal je Darstellung; ein Test kann ihn festlegen.
  const [mountedAt] = useState(() => Date.now())
  const at = now ?? mountedAt

  const cards = useMemo(
    () =>
      tutorials.flatMap((tutorial) => {
        if (!tutorial.welcome) return []
        const text = findTutorial(index, locale, tutorial.id)
        if (text === null) return []
        const steps = stepsForRole(tutorial.steps, role)
        return [{ tutorial, text, steps, phase: checklistPhase(steps, at) }]
      }),
    [tutorials, index, locale, role, at],
  )

  if (error !== null) {
    return (
      <StatusCard>
        <div className="space-y-2">
          <ErrorAlert title={t('checklist.error')} message={error} />
          <Button variant="outline" size="sm" onClick={reload}>
            {t('home.tutorials.retry')}
          </Button>
        </div>
      </StatusCard>
    )
  }
  // Beim Neu-Laden (Tab-Rueckkehr) bleibt der bisherige Stand stehen.
  if (loading && tutorials.length === 0) {
    return (
      <StatusCard>
        <LoadingState rows={4} />
      </StatusCard>
    )
  }
  const visible = cards.filter((card) => card.phase !== 'gone')
  if (visible.length === 0) return null
  return (
    <div className="flex flex-col gap-4">
      {visible.map(({ tutorial, text, steps, phase }) =>
        phase === 'done' ? (
          <DoneCard key={tutorial.id} tutorial={tutorial} text={text} />
        ) : (
          <OpenCard key={tutorial.id} tutorial={tutorial} text={text} steps={steps} state={state} />
        ),
      )}
    </div>
  )
}
