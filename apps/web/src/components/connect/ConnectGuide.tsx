import { Copy, ExternalLink } from 'lucide-react'
import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  OTHER_CLIENTS_HELP_PATH,
  claudeCodeCommand,
  claudeInstallLink,
  cursorInstallLink,
  hermesCommand,
  vscodeInstallLink,
  type ConnectClient,
} from '@/lib/installLinks'
import { cn } from '@/lib/utils'

/*
 * Gemeinsame Verbinden-Anleitung (Client-Auswahl-Spec §3) fuer den
 * Verbinden-Baustein der Agent-Seite und die Begruessung. Vorher hatten beide
 * je eine eigene Kopie; die Kopie im Dialog brach jeden Wert mit `break-all`,
 * auch den Test-Satz. Unterschiede zwischen den beiden Orten sind Props.
 *
 * Brand-Regel (Designsprache §2.2): genau eine `brand`-Aktion je Anleitung,
 * waehrend des Wartens faellt sie auf `outline` zurueck.
 */

const LINK = 'underline underline-offset-4 hover:text-foreground'
// Ziele auf Mobil >= 44 px (Spec §8), ab md die Standardhoehe.
export const CONNECT_ACTION = 'min-h-11 w-full sm:w-auto md:min-h-10'
const HINT = 'text-xs break-words text-muted-foreground'
// Platzhalter fuer Code im Satz: der Satz wird daran geteilt (kein HTML im JSON).
const CODE_MARK = '[[code]]'

export type CopyHandler = (value: string, after?: () => void) => void

export interface ConnectGuideProps {
  client: ConnectClient
  agentName: string
  /** Anzeigename des Connectors (`Who2Be – <Agent>`). */
  connectorName: string
  connectorUrl: string
  /** Shell-sicherer Servername (`who2be-<agent>`). */
  slug: string
  waiting: boolean
  /** Claude-Free-Hinweis; beim verwalteten Builder entfaellt er. */
  showFreeHint?: boolean
  onStart: () => void
  onCopy: CopyHandler
}

/**
 * Satz mit eingebettetem `<code>` am Platzhalter `{{cmd}}`. Kurze Befehle wie
 * `/reload-mcp` bleiben ganz, nur lange duerfen bei 320 px mitten im Wort brechen.
 */
function WithCode({ text, code }: { text: string; code: string }) {
  const [before = '', after = ''] = text.split(CODE_MARK)
  return (
    <>
      {before}
      <code
        className={cn(
          'rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]',
          code.length <= 16 ? 'whitespace-nowrap' : 'break-all',
        )}
      >
        {code}
      </code>
      {after}
    </>
  )
}

export function ConnectGuide({
  client,
  agentName,
  connectorName,
  connectorUrl,
  slug,
  waiting,
  showFreeHint = false,
  onStart,
  onCopy,
}: ConnectGuideProps) {
  const { t } = useTranslation('agents')
  const wsPath = useWorkspacePath()
  const leadId = useId()
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
  // Untertitel (Spec §2.3): beantwortet „Bin ich hier richtig?“.
  const lead = (
    <p id={leadId} className="text-sm break-words text-muted-foreground" data-testid="connect-lead">
      {t(`connect.lead.${client}`)}
    </p>
  )

  let guide: ReactNode
  if (client === 'claude') {
    const href = claudeInstallLink(connectorName, connectorUrl)
    guide = (
      <>
        <ol aria-describedby={leadId} className="flex list-decimal flex-col gap-2 pl-5 text-sm break-words">
          <li>{t('connect.steps.claude')}</li>
          <li>{t('connect.steps.confirm', { client: 'Claude', agent: agentName })}</li>
          <li className="space-y-2">
            {t('connect.steps.test')}
            {sentence}
          </li>
        </ol>
        <div>
          <Button asChild variant={waiting ? 'outline' : 'brand'} className={CONNECT_ACTION}>
            {/* RR7-`Link` erkennt absolute URLs und rendert einen normalen
                externen Link (Lint verbietet rohes <a>). */}
            <Link to={href} reloadDocument target="_blank" rel="noopener noreferrer" onClick={onStart}>
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
        <p className={HINT}>{t('connect.teamPlan')}</p>
        {showFreeHint ? <p className={HINT}>{t('connect.free')}</p> : null}
      </>
    )
  } else if (client === 'code' || client === 'hermes') {
    // Terminal-Wege: der Befehl ist die Hauptaktion, Kopieren startet das Warten.
    const command = client === 'code' ? claudeCodeCommand(slug, connectorUrl) : hermesCommand(slug, connectorUrl)
    guide = (
      <>
        <ol aria-describedby={leadId} className="flex list-decimal flex-col gap-3 pl-5 text-sm break-words">
          <li className="space-y-2">
            {t('connect.steps.code')}
            <CopyField
              label={t('connect.commandLabel')}
              value={command}
              copyLabel={t('connect.cta.code')}
              onCopy={(value) => onCopy(value, onStart)}
              primary={!waiting}
              mono
              breakAll
            />
          </li>
          {client === 'code' ? (
            <li>{t('connect.steps.login', { agent: agentName })}</li>
          ) : (
            <li>{t('connect.steps.hermesLogin', { agent: agentName })}</li>
          )}
          <li className="space-y-2">
            {client === 'code' ? (
              t('connect.steps.test')
            ) : (
              <span className="block">
                <WithCode text={t('connect.steps.hermesTest', { cmd: CODE_MARK })} code="/reload-mcp" />
              </span>
            )}
            {sentence}
          </li>
        </ol>
        {client === 'hermes' ? (
          <div className="flex flex-col gap-1" data-testid="connect-hints">
            <p className={HINT}>
              <WithCode
                text={t('connect.hermesProfile', { cmd: CODE_MARK })}
                code={t('connect.hermesProfileCommand')}
              />
            </p>
            <p className={HINT}>{t('connect.hermesHeadless')}</p>
          </div>
        ) : null}
      </>
    )
  } else if (client === 'editor') {
    guide = (
      <>
        <ol aria-describedby={leadId} className="flex list-decimal flex-col gap-2 pl-5 text-sm break-words">
          <li>{t('connect.steps.editor')}</li>
          <li>{t('connect.steps.login', { agent: agentName })}</li>
          <li className="space-y-2">
            {t('connect.steps.test')}
            {sentence}
          </li>
        </ol>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button asChild variant={waiting ? 'outline' : 'brand'} className={CONNECT_ACTION}>
            <Link to={cursorInstallLink(slug, connectorUrl)} reloadDocument onClick={onStart}>
              <ExternalLink aria-hidden="true" />
              {t('connect.cta.cursor')}
            </Link>
          </Button>
          <Button asChild variant="outline" className={CONNECT_ACTION}>
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
      </>
    )
  } else {
    guide = (
      <div aria-describedby={leadId} className="flex flex-col gap-3 text-sm break-words">
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
            <Button type="button" variant="outline" className={CONNECT_ACTION} onClick={onStart}>
              {t('connect.cta.other')}
            </Button>
          </div>
        )}
        <p className="text-xs">
          <Link to={wsPath(OTHER_CLIENTS_HELP_PATH)} className={LINK}>
            {t('connect.otherProfiles')}
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4" data-testid="connect-guide" data-client={client}>
      {lead}
      {guide}
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
        <p className={HINT}>{path}</p>
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
          className={cn(
            'flex min-h-10 min-w-0 flex-1 items-center rounded-md px-3 py-2 text-sm',
            breakAll ? 'break-all' : 'break-words',
            dashed ? 'border border-dashed border-input' : 'border border-input bg-muted/50',
            (mono || dashed) && 'font-mono',
          )}
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

export interface WaitingBlockProps {
  agentName: string
  clientName: string
  confirmVisible: boolean
  expired: boolean
  /** Ziel von „Klappt es nicht?“; ohne Ziel entfaellt der Link. */
  troubleshootHref?: string
  testId: string
  onConfirm: () => void
  onCheckAgain: () => void
}

export function WaitingBlock({
  agentName,
  clientName,
  confirmVisible,
  expired,
  troubleshootHref,
  testId,
  onConfirm,
  onCheckAgain,
}: WaitingBlockProps) {
  const { t } = useTranslation('agents')
  return (
    <div className="flex flex-col gap-3 rounded-md border border-dashed bg-muted/40 p-3" data-testid={testId}>
      <div className="flex items-start gap-3" role="status">
        {/* Vier Pulse, dann ruhig: unter 5 s (WCAG 2.2.2); bei reduzierter
            Bewegung greift das globale Netz und der Punkt steht still. */}
        <span
          className="mt-1.5 inline-block size-2.5 shrink-0 animate-[pulse_1s_ease-in-out_4] rounded-full bg-brand"
          aria-hidden="true"
        />
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-sm font-medium break-words">{t('connect.waiting', { agent: agentName })}</span>
          <span className="text-xs break-words text-muted-foreground">
            {expired ? t('connect.expired') : t('connect.waitingHint', { client: clientName })}
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
      {troubleshootHref !== undefined ? (
        <p className="text-xs">
          <Link to={troubleshootHref} className={LINK}>
            {t('connect.troubleshoot')}
          </Link>
        </p>
      ) : null}
    </div>
  )
}
