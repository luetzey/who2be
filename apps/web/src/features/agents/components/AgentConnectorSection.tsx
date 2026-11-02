import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ConnectGuide, WaitingBlock } from '@/components/connect/ConnectGuide'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { config } from '@/config'
import { copyToClipboard } from '@/lib/clipboard'
import { formatDateTime } from '@/lib/dates'
import { notify } from '@/lib/feedback'
import {
  CONNECT_CLIENTS,
  CONNECT_HELP_PATHS,
  agentConnectorUrl,
  serverSlug,
  type ConnectClient,
} from '@/lib/installLinks'

import { describeAgentMissing } from '../lib/activation'

// Warten auf den ersten Abruf (Onboarding-Spec §6.3, Owner O6 a): alle 5 s und
// bei Rueckkehr in den Tab nachfragen, hoechstens 10 Minuten; nach 2 Minuten
// ohne Abruf zusaetzlich „Ja, weiter“.
export const POLL_INTERVAL_MS = 5_000
export const CONFIRM_AFTER_MS = 2 * 60_000
export const POLL_LIMIT_MS = 10 * 60_000

const LINK = 'underline underline-offset-4 hover:text-foreground'

type Usage =
  | { status: 'loading' }
  | { status: 'ok'; lastUsedAt: string | null }
  | { status: 'error' }

interface Waiting {
  startedAt: number
  /** `last_used_at` beim Start; `undefined` = unbekannt, der erste Abruf setzt ihn. */
  baseline: string | null | undefined
  confirmVisible: boolean
  expired: boolean
}

type ConnectAgent = Pick<Agent, 'id' | 'name' | 'status' | 'activatable' | 'missing' | 'is_managed'>

interface AgentConnectorSectionProps {
  agent: ConnectAgent
}

/**
 * Verbinden-Baustein im Ueberblick der Agent-Seite (Onboarding P2, Spec §5.1):
 * Programmwahl, Ein-Klick-Links, Test-Satz, Warten auf den ersten Abruf und
 * Kopierfelder als Rueckfall. Die URL traegt den Agenten im Pfad (`/a/<id>`),
 * damit sie pro Agent eindeutig ist und den Agenten beim Consent bindet — die
 * Query verwirft der Client fuer den OAuth-`resource`-Parameter. Kein Token:
 * angemeldet wird per OAuth.
 *
 * Erfolgsquelle ist `last_used_at` aus der Nutzung dieses Agenten (nur
 * Server-Auslieferungen). Ein Abruf gilt als neu, wenn der Wert sich gegenueber
 * dem Stand beim Klick aendert — so spielt die Uhr des Browsers keine Rolle.
 */
export function AgentConnectorSection({ agent }: AgentConnectorSectionProps) {
  const { t } = useTranslation('agents')
  const api = useApi()
  const wsPath = useWorkspacePath()
  const titleId = useId()

  const [client, setClient] = useState<ConnectClient>('claude')
  const [usage, setUsage] = useState<Usage>({ status: 'loading' })
  const [waiting, setWaiting] = useState<Waiting | null>(null)
  // Nach Erfolg oder „Ja, weiter“ zeigt die Karte die kurze Fassung.
  const [connected, setConnected] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const inFlight = useRef(false)
  const waitingRef = useRef<Waiting | null>(null)
  useEffect(() => {
    waitingRef.current = waiting
  }, [waiting])

  const agentId = agent.id
  const connectorUrl = agentConnectorUrl(config.mcpUrl, agentId)
  const connectorName = t('connect.nameValue', { name: agent.name })
  const slug = serverSlug(agent.name)
  const clientName = t(`connect.clientName.${client}`)

  useEffect(() => {
    let alive = true
    Promise.resolve()
      .then(() => api.getAgentUsage(agentId))
      .then(
        (stats) => {
          if (alive) setUsage({ status: 'ok', lastUsedAt: stats.last_used_at })
        },
        () => {
          if (alive) setUsage({ status: 'error' })
        },
      )
    return () => {
      alive = false
    }
  }, [api, agentId])

  const check = useCallback(async () => {
    if (inFlight.current || waitingRef.current === null) return
    inFlight.current = true
    try {
      const stats = await api.getAgentUsage(agentId)
      const current = waitingRef.current
      if (current === null) return
      setUsage({ status: 'ok', lastUsedAt: stats.last_used_at })
      if (current.baseline === undefined) {
        setWaiting({ ...current, baseline: stats.last_used_at })
        return
      }
      if (stats.last_used_at !== null && stats.last_used_at !== current.baseline) {
        setWaiting(null)
        setConnected(true)
        setExpanded(false)
        setAnnouncement(t('connect.success', { agent: agent.name }))
      }
    } catch {
      // Einzelner Fehlschlag: der naechste Takt fragt erneut.
    } finally {
      inFlight.current = false
    }
  }, [api, agentId, agent.name, t])

  const startedAt = waiting?.startedAt ?? null
  const expired = waiting?.expired ?? false
  useEffect(() => {
    if (startedAt === null || expired) return
    const interval = window.setInterval(() => void check(), POLL_INTERVAL_MS)
    const confirm = window.setTimeout(() => {
      setWaiting((w) => (w !== null && w.startedAt === startedAt ? { ...w, confirmVisible: true } : w))
    }, CONFIRM_AFTER_MS)
    const stop = window.setTimeout(() => {
      setWaiting((w) => (w !== null && w.startedAt === startedAt ? { ...w, expired: true } : w))
    }, POLL_LIMIT_MS)
    // Rueckkehr aus Claude: sofort nachfragen statt bis zu 5 s zu warten.
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check()
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    return () => {
      window.clearInterval(interval)
      window.clearTimeout(confirm)
      window.clearTimeout(stop)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [startedAt, expired, check])

  function startWaiting() {
    setAnnouncement('')
    setWaiting((current) => {
      // Ein zweiter Klick verlaengert das Warten, behaelt aber den Stand.
      const baseline =
        current !== null
          ? current.baseline
          : usage.status === 'ok'
            ? usage.lastUsedAt
            : undefined
      return {
        startedAt: Date.now(),
        baseline,
        confirmVisible: current?.confirmVisible ?? false,
        expired: false,
      }
    })
  }

  function confirmManually() {
    setWaiting(null)
    setConnected(true)
    setExpanded(false)
    setAnnouncement(t('connect.status.connected'))
  }

  function copy(value: string, after?: () => void) {
    void copyToClipboard(value)
      .then(() => {
        notify.success(t('connect.copied'))
        after?.()
      })
      .catch((cause: unknown) => {
        notify.error(cause instanceof Error ? cause.message : t('connect.copyError'))
      })
  }

  const ready = agent.status === 'enabled' && agent.activatable
  const lastUsedAt = usage.status === 'ok' ? usage.lastUsedAt : null
  const isConnected = connected || lastUsedAt !== null
  const compact = isConnected && !expanded && waiting === null

  let body: ReactNode
  if (!ready) {
    body = (
      <p className="text-sm break-words" data-testid="connect-not-ready">
        {agent.missing.length > 0
          ? t('form.missing.notice', { items: describeAgentMissing(agent.missing).join(', ') })
          : t('connect.notReady.disabled')}{' '}
        <Link to={wsPath(`/agents/${encodeURIComponent(agentId)}?tab=settings`)} className={LINK}>
          {t('connect.notReady.fix')}
        </Link>
      </p>
    )
  } else if (usage.status === 'loading' && !connected) {
    body = (
      <div className="h-10 w-48 animate-pulse rounded-md bg-muted" aria-hidden="true" />
    )
  } else if (compact) {
    body = (
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm break-words text-muted-foreground" data-testid="connect-compact">
          {lastUsedAt !== null
            ? t('connect.lastFetch', { date: formatDateTime(lastUsedAt) })
            : t('connect.confirmedHint')}
        </p>
        <Button
          type="button"
          variant="link"
          className="h-auto min-h-11 justify-start px-0 md:min-h-9"
          onClick={() => setExpanded(true)}
        >
          {t('connect.addAnother')}
        </Button>
      </div>
    )
  } else {
    body = (
      <div className="flex flex-col gap-4">
        <ClientPicker value={client} onChange={setClient} />
        <ConnectGuide
          client={client}
          agentName={agent.name}
          connectorName={connectorName}
          connectorUrl={connectorUrl}
          slug={slug}
          waiting={waiting !== null}
          showFreeHint={agent.is_managed !== true}
          onStart={startWaiting}
          onCopy={copy}
        />
        {waiting !== null ? (
          <WaitingBlock
            agentName={agent.name}
            clientName={clientName}
            confirmVisible={waiting.confirmVisible || waiting.expired}
            expired={waiting.expired}
            troubleshootHref={wsPath(CONNECT_HELP_PATHS[client])}
            testId="connect-waiting"
            onConfirm={confirmManually}
            onCheckAgain={() => {
              startWaiting()
              void check()
            }}
          />
        ) : null}
        {isConnected ? (
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="min-h-11 md:min-h-9"
              onClick={() => {
                setWaiting(null)
                setExpanded(false)
              }}
            >
              {t('connect.collapse')}
            </Button>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <section aria-labelledby={titleId} data-testid="agent-connect">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 space-y-0">
          <CardTitle id={titleId}>{t('connect.title')}</CardTitle>
          {ready && (connected || usage.status === 'ok') ? (
            <span
              className="inline-flex items-center gap-2 rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground"
              data-testid="connect-status"
            >
              <span
                className="inline-block size-2 rounded-full"
                style={{
                  backgroundColor: `var(--status-${isConnected ? 'active' : 'inactive'})`,
                }}
                aria-hidden="true"
              />
              {isConnected ? t('connect.status.connected') : t('connect.status.notConnected')}
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          {body}
          <p className="sr-only" aria-live="polite" data-testid="connect-live">
            {announcement}
          </p>
        </CardContent>
      </Card>
    </section>
  )
}

// ------------------------------------------------------------- Programmwahl

function ClientPicker({
  value,
  onChange,
}: {
  value: ConnectClient
  onChange: (client: ConnectClient) => void
}) {
  const { t } = useTranslation('agents')
  const labelId = useId()
  return (
    <div className="flex flex-col gap-2">
      <span id={labelId} className="text-sm text-muted-foreground">
        {t('connect.clientQuestion')}
      </span>
      {/* Festes Raster (Client-Auswahl-Spec §2.2): unter md 2 Spalten, ab md 3,
          damit alle Zeilen gleich voll und gleich hoch sind. */}
      <div role="group" aria-labelledby={labelId} className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {CONNECT_CLIENTS.map((entry) => (
          <Button
            key={entry}
            type="button"
            size="sm"
            variant={entry === value ? 'default' : 'outline'}
            aria-pressed={entry === value}
            className="h-auto min-h-11 flex-col gap-0 whitespace-normal md:min-h-9 md:flex-row md:gap-1"
            onClick={() => onChange(entry)}
          >
            {t(`connect.client.${entry}`)}
            {entry === 'claude' ? (
              <>
                {/* Leerzeichen fuer den zugaenglichen Namen „Claude (Web, App,
                    Handy)“; im Flex-Container rendert es nicht. */}{' '}
                {/* Zusatz unter md als zweite Zeile, damit er bei 320 px nicht
                    mitten in der Klammer bricht. */}
                <span className="block text-xs font-normal opacity-75 md:inline md:text-sm md:font-medium md:opacity-100">
                  {t('connect.clientSuffix.claude')}
                </span>
              </>
            ) : null}
          </Button>
        ))}
      </div>
    </div>
  )
}
