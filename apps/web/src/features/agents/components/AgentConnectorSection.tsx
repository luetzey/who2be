// PROBE t_0d3f4203: nur fuer den Hilfe-Drift-Test-PR, wird nie gemergt.
import { Copy, ExternalLink } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { config } from '@/config'
import { copyToClipboard } from '@/lib/clipboard'
import { formatDateTime } from '@/lib/dates'
import { notify } from '@/lib/feedback'
import {
  CONNECT_CLIENTS,
  agentConnectorUrl,
  claudeCodeCommand,
  claudeInstallLink,
  cursorInstallLink,
  serverSlug,
  vscodeInstallLink,
  type ConnectClient,
} from '@/lib/installLinks'

import { describeAgentMissing } from '../lib/activation'

// Warten auf den ersten Abruf (Onboarding-Spec §6.3, Owner O6 a): alle 5 s und
// bei Rueckkehr in den Tab nachfragen, hoechstens 10 Minuten; nach 2 Minuten
// ohne Abruf zusaetzlich „Ja, weiter“.
export const POLL_INTERVAL_MS = 5_000
export const CONFIRM_AFTER_MS = 2 * 60_000
export const POLL_LIMIT_MS = 10 * 60_000

// Anker im Tutorial „Erste Schritte“ (ADR-0060), bis P7 eigene Seiten bringt.
const TROUBLESHOOT_PATH = '/help/tutorials/getting-started#connect-claude'

const LINK = 'underline underline-offset-4 hover:text-foreground'
// Ziele auf Mobil >= 44 px (Spec §8), ab md die Standardhoehe.
const ACTION = 'min-h-11 w-full sm:w-auto md:min-h-10'

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
        <ClientGuide
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
            troubleshootHref={wsPath(TROUBLESHOOT_PATH)}
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
      <div
        role="group"
        aria-labelledby={labelId}
        className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap"
      >
        {CONNECT_CLIENTS.map((entry) => (
          <Button
            key={entry}
            type="button"
            size="sm"
            variant={entry === value ? 'default' : 'outline'}
            aria-pressed={entry === value}
            className="h-auto min-h-11 whitespace-normal md:min-h-9"
            onClick={() => onChange(entry)}
          >
            {t(`connect.client.${entry}`)}
          </Button>
        ))}
      </div>
    </div>
  )
}

// -------------------------------------------------------------- Anleitung

interface ClientGuideProps {
  client: ConnectClient
  agentName: string
  connectorName: string
  connectorUrl: string
  slug: string
  waiting: boolean
  showFreeHint: boolean
  onStart: () => void
  onCopy: (value: string, after?: () => void) => void
}

function ClientGuide({
  client,
  agentName,
  connectorName,
  connectorUrl,
  slug,
  waiting,
  showFreeHint,
  onStart,
  onCopy,
}: ClientGuideProps) {
  const { t } = useTranslation('agents')
  const newTab = <span className="sr-only"> {t('connect.newTab')}</span>
  const sentence = (
    <CopyField
      label={t('connect.testLabel')}
      value={t('connect.testSentence')}
      copyLabel={t('connect.copySentence')}
      onCopy={onCopy}
      dashed
    />
  )

  if (client === 'claude') {
    const href = claudeInstallLink(connectorName, connectorUrl)
    return (
      <div className="flex flex-col gap-4">
        <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm break-words">
          <li>{t('connect.steps.claude')}</li>
          <li>{t('connect.steps.confirm', { client: 'Claude', agent: agentName })}</li>
          <li className="space-y-2">
            {t('connect.steps.test')}
            {sentence}
          </li>
        </ol>
        <div>
          <Button asChild variant={waiting ? 'outline' : 'brand'} className={ACTION}>
            {/* RR7-`Link` erkennt absolute URLs und rendert einen normalen
                externen Link (Lint verbietet rohes <a>). */}
            <Link
              to={href}
              reloadDocument
              target="_blank"
              rel="noopener noreferrer"
              onClick={onStart}
            >
              <ExternalLink aria-hidden="true" />
              {waiting ? t('connect.reopenClaude') : t('connect.cta.claude')}
              {newTab}
            </Link>
          </Button>
        </div>
        <ManualFallback
          connectorName={connectorName}
          connectorUrl={connectorUrl}
          path={t('connect.manual.claudePath')}
          onCopy={onCopy}
        />
        <p className="text-xs break-words text-muted-foreground">{t('connect.teamPlan')}</p>
        {showFreeHint ? (
          <p className="text-xs break-words text-muted-foreground">{t('connect.free')}</p>
        ) : null}
      </div>
    )
  }

  if (client === 'code') {
    const command = claudeCodeCommand(slug, connectorUrl)
    return (
      <ol className="flex list-decimal flex-col gap-3 pl-5 text-sm break-words">
        <li className="space-y-2">
          {t('connect.steps.code')}
          <CopyField
            label={t('connect.commandLabel')}
            value={command}
            copyLabel={t('connect.cta.code')}
            onCopy={(value) => onCopy(value, onStart)}
            primary={!waiting}
            breakAll
          />
        </li>
        <li>{t('connect.steps.login', { agent: agentName })}</li>
        <li className="space-y-2">
          {t('connect.steps.test')}
          {sentence}
        </li>
      </ol>
    )
  }

  if (client === 'editor') {
    return (
      <div className="flex flex-col gap-4">
        <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm break-words">
          <li>{t('connect.steps.editor')}</li>
          <li>{t('connect.steps.login', { agent: agentName })}</li>
          <li className="space-y-2">
            {t('connect.steps.test')}
            {sentence}
          </li>
        </ol>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button asChild variant={waiting ? 'outline' : 'brand'} className={ACTION}>
            <Link to={cursorInstallLink(slug, connectorUrl)} reloadDocument onClick={onStart}>
              <ExternalLink aria-hidden="true" />
              {t('connect.cta.cursor')}
            </Link>
          </Button>
          <Button asChild variant="outline" className={ACTION}>
            <Link to={vscodeInstallLink(slug, connectorUrl)} reloadDocument onClick={onStart}>
              <ExternalLink aria-hidden="true" />
              {t('connect.cta.vscode')}
            </Link>
          </Button>
        </div>
        <ManualFallback
          connectorName={slug}
          connectorUrl={connectorUrl}
          path={t('connect.manual.editorPath')}
          onCopy={onCopy}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 text-sm break-words">
      <p>{t('connect.steps.otherIntro')}</p>
      <CopyField
        label={t('connect.urlLabel')}
        value={connectorUrl}
        copyLabel={t('connect.copyUrl')}
        onCopy={onCopy}
        mono
        breakAll
      />
      <p>{t('connect.steps.otherTest')}</p>
      {sentence}
      {waiting ? null : (
        <div>
          <Button type="button" variant="outline" className={ACTION} onClick={onStart}>
            {t('connect.cta.other')}
          </Button>
        </div>
      )}
    </div>
  )
}

function ManualFallback({
  connectorName,
  connectorUrl,
  path,
  onCopy,
}: {
  connectorName: string
  connectorUrl: string
  path: string
  onCopy: (value: string) => void
}) {
  const { t } = useTranslation('agents')
  return (
    <details className="group min-w-0 rounded-md border px-3 py-2" data-testid="connect-manual">
      <summary className="flex min-h-11 cursor-pointer items-center text-sm text-muted-foreground md:min-h-9">
        {t('connect.manual.summary')}
      </summary>
      <div className="flex flex-col gap-3 pt-2">
        <CopyField
          label={t('connect.nameLabel')}
          value={connectorName}
          copyLabel={t('connect.copyName')}
          onCopy={onCopy}
        />
        <CopyField
          label={t('connect.urlLabel')}
          value={connectorUrl}
          copyLabel={t('connect.copyUrl')}
          onCopy={onCopy}
          mono
          breakAll
        />
        <p className="text-xs break-words text-muted-foreground">{path}</p>
      </div>
    </details>
  )
}

// Kopierfeld (Designsprache §10.2): Wert als `<output>` mit Label, Knopf
// daneben, unter `md` darunter. Lange URLs brechen um statt abgeschnitten zu
// werden (Responsive-Vertrag #570). `breakAll` nur fuer URLs und Befehle ohne
// Trennstelle; Text (Test-Satz, Name) bricht an Wortgrenzen (`break-words`),
// sonst zerreisst er bei 320 px mitten im Wort (Review P6).
function CopyField({
  label,
  value,
  copyLabel,
  onCopy,
  mono = false,
  dashed = false,
  primary = false,
  breakAll = false,
}: {
  label: string
  value: string
  copyLabel: string
  onCopy: (value: string) => void
  mono?: boolean
  dashed?: boolean
  primary?: boolean
  breakAll?: boolean
}) {
  const id = useId()
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <output
          id={id}
          aria-live="off"
          className={[
            'flex min-h-10 min-w-0 flex-1 items-center rounded-md px-3 py-2 text-sm',
            breakAll ? 'break-all' : 'break-words',
            dashed ? 'border border-dashed border-input' : 'border border-input bg-muted/50',
            mono || dashed ? 'font-mono' : '',
          ].join(' ')}
        >
          {value}
        </output>
        <Button
          type="button"
          size="sm"
          variant={primary ? 'brand' : 'outline'}
          className="min-h-11 w-full md:min-h-9 md:w-auto"
          onClick={() => onCopy(value)}
        >
          <Copy aria-hidden="true" />
          {copyLabel}
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- Warten

function WaitingBlock({
  agentName,
  clientName,
  confirmVisible,
  expired,
  troubleshootHref,
  onConfirm,
  onCheckAgain,
}: {
  agentName: string
  clientName: string
  confirmVisible: boolean
  expired: boolean
  troubleshootHref: string
  onConfirm: () => void
  onCheckAgain: () => void
}) {
  const { t } = useTranslation('agents')
  return (
    <div
      className="flex flex-col gap-3 rounded-md border border-dashed bg-muted/40 p-3"
      data-testid="connect-waiting"
    >
      <div className="flex items-start gap-3" role="status">
        {/* Vier Pulse, dann ruhig: unter 5 s (WCAG 2.2.2); bei reduzierter
            Bewegung greift das globale Netz und der Punkt steht still. */}
        <span
          className="mt-1.5 inline-block size-2.5 shrink-0 animate-[pulse_1s_ease-in-out_4] rounded-full bg-brand"
          aria-hidden="true"
        />
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm font-medium break-words">
            {t('connect.waiting', { agent: agentName })}
          </span>
          <span className="text-xs break-words text-muted-foreground">
            {expired
              ? t('connect.expired')
              : t('connect.waitingHint', { client: clientName })}
          </span>
        </div>
      </div>
      {confirmVisible ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <span className="text-sm">{t('connect.confirmQuestion')}</span>
          <Button type="button" variant="outline" size="sm" className="min-h-11 md:min-h-9" onClick={onConfirm}>
            {t('connect.confirmYes')}
          </Button>
          {expired ? (
            <Button type="button" variant="ghost" size="sm" className="min-h-11 md:min-h-9" onClick={onCheckAgain}>
              {t('connect.checkAgain')}
            </Button>
          ) : null}
        </div>
      ) : null}
      <p className="text-xs">
        <Link to={troubleshootHref} className={LINK}>
          {t('connect.troubleshoot')}
        </Link>
      </p>
    </div>
  )
}
