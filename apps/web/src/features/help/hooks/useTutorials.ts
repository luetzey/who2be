import { useCallback, useMemo, useRef, useState } from 'react'

import {
  listTutorials,
  patchTutorial,
  restartTutorial,
  type Tutorial,
  type TutorialStep,
  type TutorialStepState,
} from '@/api/client'
import type { WorkspaceRole } from '@/api/types'
import { useAuthToken } from '@/auth/useAuthToken'
import { useWorkspaceId } from '@/auth/useWorkspaceId'
import { useListData } from '@/hooks/useListData'
import i18n from '@/i18n'
import { notify } from '@/lib/feedback'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface TutorialsState {
  tutorials: Tutorial[]
  /** `true`, solange eine Liste geladen wird (auch beim Neu-Laden). */
  loading: boolean
  error: string | null
  reload: () => void
  /** ID des Tutorials bzw. Schritts, dessen Aenderung gerade laeuft. */
  pending: string | null
  restart: (tutorialId: string) => Promise<Tutorial | null>
  /** Antwort des Servers, `null` bei Fehler (schon gemeldet) oder gesperrt. */
  setStep: (tutorialId: string, stepId: string, state: TutorialStepState) => Promise<Tutorial | null>
}

/**
 * Tutorials des Kontos mit Fortschritt (`GET /v1/me/tutorials`, ADR-0060).
 *
 * Eine Quelle pro Ansicht: Schritte, Typen und Zustaende kommen nur vom
 * Server; Antworten auf Aenderungen ersetzen das Tutorial in der Liste, bis
 * die naechste geladene Liste sie abloest. Eine laufende Aenderung sperrt
 * weitere (`pending`), damit kein Doppel-Submit entsteht.
 */
export function useTutorials({ enabled = true }: { enabled?: boolean } = {}): TutorialsState {
  const token = useAuthToken()
  const workspaceId = useWorkspaceId()
  // `enabled: false` laedt nichts (leere Liste). Das „?“-Menue in der
  // Kopfzeile fragt erst beim ersten Oeffnen, nicht auf jeder Seite.
  const loader = useCallback(
    () => (enabled ? listTutorials(token, workspaceId) : Promise.resolve<Tutorial[]>([])),
    [enabled, token, workspaceId],
  )
  const list = useListData<Tutorial>(loader)
  // Antworten auf Aenderungen gelten nur fuer die Liste, auf der sie entstanden
  // sind (`base`): kommt eine neue Liste vom Server, ist sie der neuere Stand.
  // So bleibt beim Neu-Laden (Tab-Rueckkehr) nichts kurz auf dem alten Stand
  // stehen, und eine Antwort aus einem anderen Workspace greift nie.
  const [updated, setUpdated] = useState<{
    base: Tutorial[] | null
    items: Record<string, Tutorial>
  }>({ base: null, items: {} })
  const [pending, setPending] = useState<string | null>(null)
  const busy = useRef(false)
  const { data, reload } = list

  const tutorials = useMemo(() => {
    const items = updated.base === data ? updated.items : {}
    return data.map((item) => items[item.id] ?? item)
  }, [data, updated])

  const replace = useCallback(
    (next: Tutorial) => {
      setUpdated((previous) => ({
        base: data,
        items: { ...(previous.base === data ? previous.items : {}), [next.id]: next },
      }))
    },
    [data],
  )

  const run = useCallback(
    async (key: string, action: () => Promise<Tutorial>): Promise<Tutorial | null> => {
      if (busy.current) return null
      busy.current = true
      setPending(key)
      try {
        const next = await action()
        replace(next)
        return next
      } catch (cause) {
        notify.error(describeError(cause))
        return null
      } finally {
        busy.current = false
        setPending(null)
      }
    },
    [replace],
  )

  const restart = useCallback(
    (tutorialId: string) => run(tutorialId, () => restartTutorial(token, workspaceId, tutorialId)),
    [run, token, workspaceId],
  )

  const setStep = useCallback(
    (tutorialId: string, stepId: string, state: TutorialStepState) =>
      run(stepId, () => patchTutorial(token, workspaceId, tutorialId, { step_id: stepId, state })),
    [run, token, workspaceId],
  )

  return { tutorials, loading: list.loading, error: list.error, reload, pending, restart, setStep }
}

/** Erledigte bzw. uebersprungene Schritte (alles, was nicht mehr offen ist). */
export function finishedSteps(tutorial: Pick<Tutorial, 'steps'>): number {
  return tutorial.steps.filter((step) => step.state !== 'open').length
}

/**
 * Begonnen = ein Schritt ausser dem Startvorsprung ist nicht mehr offen. Nur
 * dann geht beim Neustart Fortschritt verloren, und nur dann fragt die
 * Oberflaeche vorher nach.
 */
export function tutorialStarted(tutorial: Pick<Tutorial, 'steps'>): boolean {
  return tutorial.steps.some((step) => step.type !== 'head_start' && step.state !== 'open')
}

/** Schritte, die eine Rolle nicht selbst erledigen kann (viewer legt keine Agenten an). */
const AGENT_STEP_TYPES: ReadonlySet<TutorialStep['type']> = new Set([
  'agent_created',
  'own_agent_mcp_call',
])

/** Sichtbare Schritte je Rolle; viewer sieht keine Agent-Schritte. */
export function stepsForRole(steps: TutorialStep[], role: WorkspaceRole | null): TutorialStep[] {
  return role === 'viewer' ? steps.filter((step) => !AGENT_STEP_TYPES.has(step.type)) : steps
}

/**
 * Router-State fuer Spruenge aus dem „?“-Menue (Onboarding P5). Die Ziel-
 * seite liest ihn und setzt den Fokus bzw. laedt neu.
 * - `focusTutorial`: Dashboard, Fokus auf die Startliste dieses Tutorials.
 * - `replayWelcome`: Dashboard, Begruessung erneut zeigen (liest P6).
 * - `helpFocus`: Hilfe-Startseite, Fokus ins Suchfeld bzw. auf „Tutorials“.
 */
export interface HelpNavigationState {
  focusTutorial?: string
  replayWelcome?: boolean
  helpFocus?: 'search' | 'tutorials'
}

/** Liest {@link HelpNavigationState} aus `location.state` (unbekanntes faellt weg). */
export function readHelpNavigationState(state: unknown): HelpNavigationState {
  if (typeof state !== 'object' || state === null) return {}
  const raw = state as Record<string, unknown>
  const result: HelpNavigationState = {}
  if (typeof raw.focusTutorial === 'string') result.focusTutorial = raw.focusTutorial
  if (raw.replayWelcome === true) result.replayWelcome = true
  if (raw.helpFocus === 'search' || raw.helpFocus === 'tutorials') result.helpFocus = raw.helpFocus
  return result
}
