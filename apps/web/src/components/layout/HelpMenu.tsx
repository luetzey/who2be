import { CircleHelp } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

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
 * Der Punkt fuer ungesehene Neuigkeiten fehlt hier bewusst; er kommt mit
 * `news_seen_at` am Konto (eigene Karte).
 */

const ITEM = 'min-h-11 md:min-h-9'

export function HelpMenu() {
  const { t } = useTranslation('help')
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
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
            className="h-11 w-11 md:h-9 md:w-9"
            aria-label={t('menu.label')}
            data-testid="help-menu-trigger"
          >
            <CircleHelp className="h-5 w-5" aria-hidden="true" />
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
