import { ExternalLink } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { listTutorials, patchTutorial, type Tutorial } from '@/api/client'
import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { useAuthToken } from '@/auth/useAuthToken'
import { useWorkspaceId } from '@/auth/useWorkspaceId'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { CONNECT_ACTION, ConnectGuide, WaitingBlock } from '@/components/connect/ConnectGuide'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { config } from '@/config'
import { useCookieConsent } from '@/features/legal/layout'
import { findTutorial, helpIndex, toHelpLocale } from '@/help/helpIndex'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'
import {
  CONNECT_CLIENTS,
  agentConnectorUrl,
  claudeInstallLink,
  serverSlug,
  type ConnectClient,
} from '@/lib/installLinks'
import { cn } from '@/lib/utils'

import {
  connectStepDone,
  WELCOME_CONFIRM_AFTER_MS,
  WELCOME_POLL_INTERVAL_MS,
  WELCOME_POLL_LIMIT_MS,
} from '../welcome'
import { readHelpNavigationState } from '../hooks/useTutorials'
import { SuccessScene, WelcomeScene } from './WelcomeScene'

/*
 * Begruessung (Onboarding P6, Spec §3.1, Variante B): ein Dialog mit drei
 * Ansichten — Begruessung, Verbinden, Erfolg.
 *
 * Eine Quelle pro Ansicht: der Erfolg kommt nur aus `GET /v1/me/tutorials`
 * (erster Schritt vom Typ `first_mcp_call` ist `done`), dieselbe Quelle wie
 * die Startliste. Der Builder kommt aus der Agentenliste (`is_managed`), die
 * Links aus `lib/installLinks` — ohne Token, angemeldet wird per OAuth. Die
 * Texte zum Verbinden teilt der Dialog mit dem Verbinden-Baustein der
 * Agent-Seite (`agents:connect.*`).
 */

type View = 'welcome' | 'connect' | 'success'

type Builder =
  | { status: 'loading' }
  | { status: 'ready'; agent: Pick<Agent, 'id' | 'name'> }
  | { status: 'missing' }

interface Waiting {
  startedAt: number
  confirmVisible: boolean
  expired: boolean
}

const LINK = 'underline underline-offset-4 hover:text-foreground'
const ACTION = CONNECT_ACTION
// Chips „Ich nutze“: alle Programme ausser Claude, das der Hauptknopf traegt
// (Client-Auswahl-Spec §3). Reihenfolge aus `CONNECT_CLIENTS`.
const ALT_CLIENTS = CONNECT_CLIENTS.filter((entry) => entry !== 'claude')
// Programme mit eigenem Namen in der Erfolgs-Szene; sonst „Claude & Co.“.
const NAMED_CLIENTS: ReadonlySet<ConnectClient> = new Set(['claude', 'code', 'hermes'])

function useBuilder(enabled: boolean): Builder {
  const api = useApi()
  const [builder, setBuilder] = useState<Builder>({ status: 'loading' })
  useEffect(() => {
    if (!enabled) return
    let alive = true
    api.listAgents().then(
      (agents) => {
        if (!alive) return
        const found = agents.find(
          (agent) => agent.is_managed === true && agent.status === 'enabled' && agent.activatable,
        )
        setBuilder(found === undefined ? { status: 'missing' } : { status: 'ready', agent: found })
      },
      () => {
        if (alive) setBuilder({ status: 'missing' })
      },
    )
    return () => {
      alive = false
    }
  }, [api, enabled])
  return builder
}

export interface WelcomeDialogProps {
  open: boolean
  tutorialId: string
  /** Schliessen auf jedem Weg (Ueberspringen, Esc, ✕, „Weiter“). */
  onClose: () => void
}

export function WelcomeDialog({ open, tutorialId, onClose }: WelcomeDialogProps) {
  const { t, i18n } = useTranslation('help')
  const { t: ta } = useTranslation('agents')
  const token = useAuthToken()
  const workspaceId = useWorkspaceId()
  const builder = useBuilder(open)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [view, setView] = useState<View>('welcome')
  const [client, setClient] = useState<ConnectClient>('claude')
  const [waiting, setWaiting] = useState<Waiting | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const inFlight = useRef(false)

  // Fokus auf die Ueberschrift beim Oeffnen und bei jedem Ansichtswechsel (Spec §8).
  useEffect(() => {
    if (!open) return
    const id = window.requestAnimationFrame(() => headingRef.current?.focus())
    return () => window.cancelAnimationFrame(id)
  }, [open, view])

  const check = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const tutorials = await listTutorials(token, workspaceId)
      if (connectStepDone(tutorials.find((item) => item.id === tutorialId))) {
        setWaiting(null)
        setView('success')
        setAnnouncement(t('welcome.success.title'))
      }
    } catch {
      // Einzelner Fehlschlag: der naechste Takt fragt erneut.
    } finally {
      inFlight.current = false
    }
  }, [token, workspaceId, tutorialId, t])

  const startedAt = waiting?.startedAt ?? null
  const expired = waiting?.expired ?? false
  const polling = open && view === 'connect' && startedAt !== null && !expired
  useEffect(() => {
    if (!polling) return
    // Antworten nach dem Ende (Schliessen, Unmount, Erfolg) zaehlen nicht mehr.
    let alive = true
    const tick = () => {
      if (alive) void check()
    }
    const interval = window.setInterval(tick, WELCOME_POLL_INTERVAL_MS)
    const confirm = window.setTimeout(() => {
      setWaiting((w) => (w !== null && w.startedAt === startedAt ? { ...w, confirmVisible: true } : w))
    }, WELCOME_CONFIRM_AFTER_MS)
    const stop = window.setTimeout(() => {
      setWaiting((w) => (w !== null && w.startedAt === startedAt ? { ...w, expired: true } : w))
    }, WELCOME_POLL_LIMIT_MS)
    // Rueckkehr aus Claude: sofort nachfragen statt bis zu 5 s zu warten.
    const onVisible = () => {
      if (document.visibilityState === 'visible') tick()
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    return () => {
      alive = false
      window.clearInterval(interval)
      window.clearTimeout(confirm)
      window.clearTimeout(stop)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [polling, startedAt, check])

  function startWaiting() {
    setView('connect')
    setWaiting((current) => ({
      startedAt: Date.now(),
      confirmVisible: current?.confirmVisible ?? false,
      expired: false,
    }))
  }

  function choose(next: ConnectClient) {
    setClient(next)
    setView('connect')
  }

  function copy(value: string, after?: () => void) {
    void copyToClipboard(value)
      .then(() => {
        notify.success(ta('connect.copied'))
        after?.()
      })
      .catch((cause: unknown) => {
        notify.error(cause instanceof Error ? cause.message : ta('connect.copyError'))
      })
  }

  const locale = toHelpLocale(i18n.resolvedLanguage ?? i18n.language)
  const listTitle = findTutorial(helpIndex, locale, tutorialId)?.title ?? t('checklist.title')
  const agentName = builder.status === 'ready' ? builder.agent.name : 'Builder'
  const clientName = ta(`connect.clientName.${client}`)
  const connector =
    builder.status === 'ready'
      ? {
          url: agentConnectorUrl(config.mcpUrl, builder.agent.id),
          name: ta('connect.nameValue', { name: builder.agent.name }),
          slug: serverSlug(builder.agent.name),
        }
      : null

  const heading = (text: string) => (
    <DialogTitle
      ref={headingRef}
      tabIndex={-1}
      className="text-xl leading-tight break-words focus-visible:outline-none"
    >
      {text}
    </DialogTitle>
  )

  let body
  if (view === 'welcome') {
    body = (
      <>
        <TopRow step={1}>
          <Button type="button" variant="ghost" size="sm" className="min-h-11 md:min-h-9" onClick={onClose}>
            {t('welcome.skip')}
          </Button>
        </TopRow>
        <WelcomeScene />
        <div className="space-y-2">
          {heading(t('welcome.title'))}
          <DialogDescription className="text-base">
            {t('welcome.body')}
          </DialogDescription>
        </div>
        <div>
          {connector !== null ? (
            <Button asChild variant="brand" size="lg" className={cn(ACTION, 'px-6')}>
              {/* RR7-`Link` rendert absolute URLs als normalen externen Link. */}
              <Link
                to={claudeInstallLink(connector.name, connector.url)}
                reloadDocument
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => {
                  setClient('claude')
                  startWaiting()
                }}
              >
                <ExternalLink aria-hidden="true" />
                {ta('connect.cta.claude')}
                <span className="sr-only"> {ta('connect.newTab')}</span>
              </Link>
            </Button>
          ) : (
            <Button
              type="button"
              variant="brand"
              size="lg"
              className={cn(ACTION, 'px-6')}
              disabled={builder.status === 'loading'}
              onClick={() => choose('claude')}
            >
              {ta('connect.cta.claude')}
            </Button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={t('welcome.altGroup')}>
          <span className="mr-1 text-sm text-muted-foreground">{t('welcome.altLabel')}</span>
          {ALT_CLIENTS.map((entry) => (
            <Button
              key={entry}
              type="button"
              variant="outline"
              size="sm"
              className="h-auto min-h-11 rounded-full whitespace-normal md:min-h-9"
              onClick={() => choose(entry)}
            >
              {ta(`connect.client.${entry}`)}
            </Button>
          ))}
        </div>
      </>
    )
  } else if (view === 'connect') {
    body = (
      <>
        <TopRow
          step={2}
          back={
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => {
                setWaiting(null)
                setView('welcome')
              }}
            >
              {t('welcome.back')}
            </Button>
          }
        >
          <Button type="button" variant="ghost" size="sm" className="min-h-11 md:min-h-9" onClick={onClose}>
            {t('welcome.later')}
          </Button>
        </TopRow>
        <div className="space-y-2">
          {heading(t('welcome.connect.title', { agent: agentName, client: clientName }))}
          <DialogDescription>
            {t('welcome.connect.intro', { agent: agentName })}
          </DialogDescription>
        </div>
        {connector === null ? (
          builder.status === 'loading' ? (
            <div className="h-10 w-48 animate-pulse rounded-md bg-muted" aria-hidden="true" />
          ) : (
            <BuilderMissing />
          )
        ) : (
          <ConnectGuide
            client={client}
            agentName={agentName}
            connectorName={connector.name}
            connectorUrl={connector.url}
            slug={connector.slug}
            waiting={waiting !== null}
            onStart={startWaiting}
            onCopy={copy}
          />
        )}
        {waiting !== null ? (
          <WaitingBlock
            agentName={agentName}
            clientName={clientName}
            confirmVisible={waiting.confirmVisible || waiting.expired}
            expired={waiting.expired}
            testId="welcome-waiting"
            onConfirm={onClose}
            onCheckAgain={() => {
              startWaiting()
              void check()
            }}
          />
        ) : null}
      </>
    )
  } else {
    body = (
      <>
        <TopRow />
        <SuccessScene
          agentName={agentName}
          clientName={
            NAMED_CLIENTS.has(client)
              ? ta(`connect.clientName.${client}`)
              : t('welcome.scene.client')
          }
        />
        <div className="space-y-2">
          {heading(t('welcome.success.title'))}
          <DialogDescription className="text-base">
            {t('welcome.success.body', { agent: agentName })}
          </DialogDescription>
        </div>
        <p className="rounded-md border bg-muted/40 p-3 text-sm break-words">
          <strong className="font-semibold">{t('welcome.success.nextLabel')}</strong>{' '}
          {t('welcome.success.next', { agent: agentName })}
        </p>
        <div>
          <Button type="button" variant="brand" size="lg" className={cn(ACTION, 'px-6')} onClick={onClose}>
            {t('welcome.success.cta', { title: listTitle })}
          </Button>
        </div>
      </>
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        // Esc und ✕ wirken wie „Überspringen“.
        if (!next) onClose()
      }}
    >
      <DialogContent
        data-testid="welcome-dialog"
        data-view={view}
        // Kein Schliessen per Hintergrund-Klick (versehentliches Wegklicken, Spec §6.2).
        onPointerDownOutside={(event) => event.preventDefault()}
        onInteractOutside={(event) => event.preventDefault()}
        // Fokus setzt der Effekt oben auf die Ueberschrift; beim Schliessen
        // fuehrt die Seite ihn auf die Startliste.
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        className={cn(
          // < md Vollbild (Spec §8), ab md 600 px.
          'h-dvh max-h-dvh w-screen max-w-none content-start gap-5 rounded-none border-0 p-5 sm:rounded-none',
          'md:h-auto md:max-h-[calc(100dvh-2rem)] md:w-[calc(100vw-2rem)] md:max-w-[600px] md:rounded-xl md:border md:p-6',
        )}
      >
        {body}
        <p className="sr-only" aria-live="polite" data-testid="welcome-live">
          {announcement}
        </p>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------ Kopfzeile

/** Seitenanzeige (2 Punkte) links, Aktion rechts; Platz fuer das ✕ des Dialogs. */
function TopRow({ step, back, children }: { step?: 1 | 2; back?: ReactNode; children?: ReactNode }) {
  return (
    <div className="-mt-1 flex min-h-11 items-center justify-between gap-2 pr-8">
      <div className="flex items-center gap-2">
        {back}
        {step !== undefined ? (
          <div className="flex gap-1.5" aria-hidden="true">
            {[1, 2].map((dot) => (
              <span
                key={dot}
                className={cn(
                  'h-1.5 rounded-full',
                  dot === step ? 'w-4 bg-foreground' : 'w-1.5 bg-muted-foreground/40',
                )}
              />
            ))}
          </div>
        ) : null}
      </div>
      {children}
    </div>
  )
}

function BuilderMissing() {
  const { t } = useTranslation('help')
  const wsPath = useWorkspacePath()
  return (
    <p className="text-sm break-words" data-testid="welcome-builder-missing">
      {t('welcome.connect.missing')}{' '}
      <Link to={wsPath('/agents')} className={LINK}>
        {t('checklist.openAgents')}
      </Link>
    </p>
  )
}

// ------------------------------------------------------------ Steuerung

/**
 * Eigener persoenlicher Workspace = aktiver Workspace gehoert zur Org
 * `kind='personal'` und der Nutzer ist dort admin (PM W3 a). Wer in einem
 * Team-Workspace landet (Einladung), bekommt nur die Startliste (Owner O2 a).
 */
function useOwnPersonalWorkspace(): boolean {
  const { me } = useSession()
  const workspaceId = useWorkspaceId()
  if (me === null || workspaceId === '') return false
  for (const org of me.organizations) {
    const membership = org.workspaces.find((ws) => ws.id === workspaceId)
    if (membership !== undefined) return org.kind === 'personal' && membership.role === 'admin'
  }
  return false
}

/**
 * Haengt die Begruessung ins Dashboard (Spec §10.1, nicht in die AppShell) und
 * entscheidet, wann sie aufgeht:
 * - automatisch einmal, wenn `welcome_seen_at` leer ist und der aktive
 *   Workspace der eigene persoenliche ist; beim Oeffnen setzt sie
 *   `welcome_seen` (einmal, kein Doppel-Submit), damit Neuladen sie nicht
 *   wieder oeffnet;
 * - immer nach „Einführung erneut starten“ (Router-State `replayWelcome`,
 *   einmal je Navigation);
 * - nie ueber dem Cookie-Hinweis: sie wartet, bis er bestaetigt ist.
 * Schliessen fuehrt den Fokus per Router-State auf die Startliste, die dabei
 * neu laedt.
 */
export function DashboardWelcome() {
  const token = useAuthToken()
  const workspaceId = useWorkspaceId()
  const location = useLocation()
  const navigate = useNavigate()
  const { isDecided } = useCookieConsent()
  const personal = useOwnPersonalWorkspace()
  const replayRequested = readHelpNavigationState(location.state).replayWelcome === true
  const [tutorial, setTutorial] = useState<Tutorial | null>(null)
  // Automatik: einmal je Seitenleben; „Einführung erneut starten“: einmal je
  // Navigation (Router-Key). Beides abgeleitet statt per Effekt gesetzt.
  const [autoDismissed, setAutoDismissed] = useState(false)
  const [replayClosedKey, setReplayClosedKey] = useState<string | null>(null)
  const seenSent = useRef(false)

  // Eigene Abfrage nur, wenn die Begruessung ueberhaupt in Frage kommt.
  const wanted = personal || replayRequested
  useEffect(() => {
    if (!wanted) return
    let alive = true
    listTutorials(token, workspaceId).then(
      (items) => {
        if (alive) setTutorial(items.find((item) => item.welcome) ?? null)
      },
      () => {
        // Ohne Liste keine Begruessung; die Startliste meldet den Fehler selbst.
      },
    )
    return () => {
      alive = false
    }
  }, [wanted, token, workspaceId])

  const ready = tutorial !== null && isDecided
  const replayOpen = ready && replayRequested && replayClosedKey !== location.key
  const autoOpen = ready && personal && !autoDismissed && tutorial.welcome_seen_at === null
  const open = replayOpen || autoOpen

  // Vermerk beim ersten automatischen Oeffnen, damit Neuladen sie nicht
  // wieder oeffnet. Einmal je Seitenleben, kein Doppel-Submit.
  useEffect(() => {
    if (!autoOpen || tutorial === null || seenSent.current) return
    seenSent.current = true
    patchTutorial(token, workspaceId, tutorial.id, { welcome_seen: true }).catch(() => {
      // Ohne Vermerk erscheint die Begruessung beim naechsten Laden erneut.
    })
  }, [autoOpen, tutorial, token, workspaceId])

  if (tutorial === null || !open) return null
  // Nur offen gemountet: jedes Oeffnen startet frisch (Ansicht, Wartezeit),
  // und nach dem Schliessen laeuft kein Takt weiter.
  return (
    <WelcomeDialog
      open={open}
      tutorialId={tutorial.id}
      onClose={() => {
        setAutoDismissed(true)
        setReplayClosedKey(location.key)
        // `replace`: Zurueck oeffnet die Begruessung nicht noch einmal.
        void navigate(
          { pathname: location.pathname, search: location.search },
          { replace: true, state: { focusTutorial: tutorial.id } },
        )
      }}
    />
  )
}
