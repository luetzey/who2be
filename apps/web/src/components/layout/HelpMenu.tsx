import { CircleHelp } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useSession } from '@/auth/session-context'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { RestartTutorialDialog } from '@/components/help/RestartTutorialDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  finishedSteps,
  type HelpNavigationState,
  stepsForRole,
  tutorialStarted,
  useTutorials,
} from '@/features/help/hooks/useTutorials'
import { notify } from '@/lib/feedback'

/*
 * „?“-Menue in der Kopfzeile, links neben der Glocke (Onboarding P5, Spec
 * §5.2). Reihenfolge: Erste Schritte (nur solange offen) · Tutorials · Hilfe
 * durchsuchen · Was ist neu · Einfuehrung erneut starten · Trenner · Problem
 * melden.
 *
 * Die Tutorials laedt das Menue erst beim ersten Oeffnen (und bei jedem
 * weiteren Oeffnen neu), nicht auf jeder Seite. Es kennt keine Tutorial-ID:
 * „Erste Schritte“ ist das Tutorial mit `welcome: true` aus der API. Der Text
 * kommt aus i18n, nicht aus dem Hilfe-Markdown — so zieht die Kopfzeile den
 * Hilfe-Index nicht in den Haupt-Chunk.
 *
 * Der Punkt am „?“ zeigt ungesehene Neuigkeiten (Spec §5.4), siehe
 * {@link useUnseenNews}.
 */

const ITEM = 'min-h-11 md:min-h-9'

/** Ohne `news_seen_at` zaehlen nur Eintraege der letzten 14 Tage (Spec §5.4). */
const NEWS_FRESH_MS = 14 * 24 * 60 * 60 * 1000

type HelpIndexModule = typeof import('@/help/helpIndex')

/**
 * Regel fuer den Punkt (Spec §5.4, ADR-0060 §4), auf den Eintragsdaten aus
 * dem Loader von P5 (`src/help/news/`, keine zweite Quelle):
 *
 * - mit `news_seen_at`: ein Eintrag mit Datum danach;
 * - ohne: ein Eintrag nach der Kontoanlage `created_at`, hoechstens 14 Tage alt;
 * - ohne beide (Token-Pfad, alte API): kein Punkt.
 *
 * Ein Eintragsdatum zaehlt ab 00:00 UTC des Tages; ein Eintrag vom Tag des
 * letzten Besuchs gilt damit als gesehen. Unlesbare Zeitpunkte zeigen keinen
 * Punkt — lieber keiner als ein falscher.
 */
function unseen(dates: readonly string[], seenAt: string | null, createdAt: string | null, now: number) {
  const times = dates.map((date) => Date.parse(date)).filter((time) => !Number.isNaN(time))
  if (seenAt !== null) {
    const seen = Date.parse(seenAt)
    return !Number.isNaN(seen) && times.some((time) => time > seen)
  }
  if (createdAt === null) return false
  const created = Date.parse(createdAt)
  return !Number.isNaN(created) && times.some((time) => time > created && time >= now - NEWS_FRESH_MS)
}

/**
 * `true`, solange es ungesehene Neuigkeiten gibt. Der Hilfe-Index wird erst
 * nach dem ersten Rendern und nur bei bekanntem Konto-Stand nachgeladen
 * (eigener Chunk) — die Kopfzeile zieht ihn so nicht in den Haupt-Chunk.
 * `news_seen_at` kommt aus `/v1/me`; die Seite „Was ist neu“ setzt den Wert
 * und laedt `/v1/me` neu, dann verschwindet der Punkt.
 */
function useUnseenNews(): boolean {
  const { me } = useSession()
  const seenAt = me?.news_seen_at ?? null
  const createdAt = me?.created_at ?? null
  const known = seenAt !== null || createdAt !== null
  const [now] = useState(() => Date.now())
  const [help, setHelp] = useState<HelpIndexModule | null>(null)
  useEffect(() => {
    if (!known || help !== null) return
    let cancelled = false
    void import('@/help/helpIndex').then((mod) => {
      if (!cancelled) setHelp(mod)
    })
    return () => {
      cancelled = true
    }
  }, [known, help])
  if (help === null || !known) return false
  return unseen(
    help.helpIndex.news.map((item) => item.date),
    seenAt,
    createdAt,
    now,
  )
}

export function HelpMenu() {
  const { t } = useTranslation('help')
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const hasNews = useUnseenNews()
  const [opened, setOpened] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const { tutorials, loading, error, reload, pending, restart, setStep } = useTutorials({
    enabled: opened,
  })

  // Beim erneuten Oeffnen bleibt der bisherige Stand stehen, bis die neue
  // Liste da ist (kein Flackern der Eintraege).
  const ready = opened && error === null && !(loading && tutorials.length === 0)
  const welcome = ready ? (tutorials.find((tutorial) => tutorial.welcome) ?? null) : null
  const steps = welcome === null ? [] : stepsForRole(welcome.steps, role)
  // Sichtbar, solange nicht alles erledigt ist — auch nach „Ausblenden“
  // (dann sind die offenen Schritte uebersprungen), Spec §5.2.
  const showFirstSteps = steps.some((step) => step.state !== 'done')
  const firstStepsLabel = t('menu.firstSteps')

  function onOpenChange(open: boolean) {
    if (!open) return
    if (opened) reload()
    else setOpened(true)
  }

  function go(path: string, state?: HelpNavigationState) {
    void navigate(wsPath(path), state === undefined ? undefined : { state })
  }

  /**
   * „Erste Schritte“: ist die Startliste ausgeblendet (kein Schritt offen),
   * holt der Eintrag sie zurueck, indem er die uebersprungenen Schritte wieder
   * oeffnet. Erledigtes bleibt erledigt; nacheinander, der Hook sperrt
   * parallele Aenderungen.
   */
  async function showChecklist() {
    if (welcome === null) return
    if (!steps.some((step) => step.state === 'open')) {
      for (const step of steps) {
        if (step.state !== 'skipped') continue
        if ((await setStep(welcome.id, step.id, 'open')) === null) return
      }
    }
    go('/dashboard', { focusTutorial: welcome.id })
  }

  async function replay() {
    if (welcome === null) return
    const result = await restart(welcome.id)
    if (result === null) return
    setConfirmOpen(false)
    notify.success(t('menu.replayDone'))
    go('/dashboard', { replayWelcome: true, focusTutorial: result.id })
  }

  function onReplaySelect() {
    if (welcome === null) return
    // Rueckfrage nur, wenn dabei Fortschritt verloren geht.
    if (tutorialStarted(welcome)) setConfirmOpen(true)
    else void replay()
  }

  return (
    <>
      <DropdownMenu onOpenChange={onOpenChange}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="relative h-11 w-11 md:h-9 md:w-9"
            aria-label={hasNews ? t('menu.labelUnseen') : t('menu.label')}
            data-testid="help-menu-trigger"
          >
            <CircleHelp className="h-5 w-5" aria-hidden="true" />
            {hasNews ? (
              // Vorgelesen wird der Punkt ueber das `aria-label` (wie die Glocke).
              <span
                aria-hidden="true"
                data-testid="help-menu-news-dot"
                className="absolute top-2.5 right-2.5 h-2 w-2 rounded-full bg-brand ring-2 ring-background md:top-1.5 md:right-1.5"
              />
            ) : null}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          collisionPadding={8}
          className="w-[calc(100vw-1rem)] sm:w-72"
          data-testid="help-menu"
        >
          {showFirstSteps && welcome !== null ? (
            <DropdownMenuItem
              className={ITEM}
              disabled={pending !== null}
              onSelect={() => void showChecklist()}
            >
              <span className="flex-1">{firstStepsLabel}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {t('menu.firstStepsProgress', { done: finishedSteps({ steps }), total: steps.length })}
              </span>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem className={ITEM} onSelect={() => go('/help', { helpFocus: 'tutorials' })}>
            {t('menu.tutorials')}
          </DropdownMenuItem>
          <DropdownMenuItem className={ITEM} onSelect={() => go('/help', { helpFocus: 'search' })}>
            {t('menu.search')}
          </DropdownMenuItem>
          <DropdownMenuItem className={ITEM} onSelect={() => go('/help/neu')}>
            {t('menu.news')}
          </DropdownMenuItem>
          <DropdownMenuItem
            className={ITEM}
            disabled={welcome === null || pending !== null}
            onSelect={onReplaySelect}
          >
            {t('menu.replay')}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className={ITEM} onSelect={() => go('/feedback/report')}>
            {t('menu.problem')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <RestartTutorialDialog
        open={confirmOpen}
        title={firstStepsLabel}
        busy={pending !== null}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void replay()}
      />
    </>
  )
}
