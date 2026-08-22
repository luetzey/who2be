import { Link2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useSearchParams } from 'react-router-dom'

import { ApiError, createApi, oauthConsent, oauthConsentPreview } from '@/api/client'
import type { OAuthConsentPreviewAgent } from '@/api/client'
import type { Agent } from '@/api/types'
import { useAuthToken } from '@/auth/useAuthToken'
import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'

// Public-Route (ADR-0034-Folge): Consent-Screen des Who2Be-OAuth-Servers. Ein
// eingeloggter User autorisiert einen LLM-Client (Claude/ChatGPT) fuer GENAU
// einen Agenten — der ausgegebene Token erbt dessen Read-Scope + Tool-Policy.
//
// Hard-Lock (WP2/Issue #405): trug die Connector-URL `?agent=<uuid>`, ist der
// Agent im signierten Blob festgelegt — keine Auswahl, der serverseitige
// Consent bindet genau diesen Agenten. Ob ein Lock vorliegt und ob der
// eingeloggte User den gebundenen Agenten aufloesen kann (er kann in JEDER
// seiner Workspace-Memberships liegen, nicht nur im Default-Workspace), klaert
// ausschliesslich `POST /oauth/consent/preview` — die Seite rät das nicht mehr
// selbst aus dem Blob + der Default-Workspace-Agentenliste (das war Fehler 1:
// Rohe UUID statt Name, wenn der Agent in einem anderen Workspace liegt).
// `listAgents` (Dropdown) wird nur noch im ungesperrten Fall geladen — im
// Lock-Fall ist sie unnoetig und war die Ursache von Fehler 2 (leerer
// Default-Workspace blockierte den Consent, obwohl der gelockte Agent
// anderswo existierte und der User berechtigt war).
export function OAuthConsentPage() {
  const { t } = useTranslation('auth')
  const { session, me } = useSession()
  const authToken = useAuthToken()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const requestBlob = searchParams.get('request') ?? ''

  const { clientName, redirectHost } = readBlobInfo(requestBlob)

  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // `null` = Preview noch nicht beantwortet (oder fehlgeschlagen); danach
  // autoritativ true/false laut Server.
  const [locked, setLocked] = useState<boolean | null>(null)
  const [lockedAgent, setLockedAgent] = useState<OAuthConsentPreviewAgent | null>(null)

  const workspaceId = me?.default_workspace_id ?? null

  // Preview zuerst: klaert den Lock-Status autoritativ (ueber alle
  // Memberships des Users), unabhaengig vom Default-Workspace.
  useEffect(() => {
    if (session === null || requestBlob === '') {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    oauthConsentPreview(authToken, { request: requestBlob })
      .then((result) => {
        if (cancelled) return
        // Streng auf `true` normalisieren (nicht nur truthy) — der zweite
        // Effekt vergleicht `locked !== false` und muss sonst auf einem
        // unerwarteten Response-Shape haengen bleiben statt sauber in den
        // ungesperrten Pfad zu fallen.
        const isLocked = result.locked === true
        setLocked(isLocked)
        setLockedAgent(isLocked ? (result.agent ?? null) : null)
        if (isLocked) {
          // Gesperrt: aufloesbar ⇒ dessen id vormerken, sonst bleibt Approve
          // gesperrt (siehe Render). In beiden Faellen ist die Preview die
          // letzte Anfrage — fertig geladen.
          setSelectedAgentId(result.agent?.id ?? '')
          setLoading(false)
        }
        // Ungesperrt: die Agentenliste (zweiter Effekt) laedt weiter — bis
        // dahin bleibt `loading` true.
      })
      .catch((cause) => {
        if (cancelled) return
        setError(
          cause instanceof ApiError && cause.status === 400
            ? t('connector.invalidRequest')
            : t('connector.error'),
        )
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [session, requestBlob, authToken, t])

  // Nur im ungesperrten Fall: Dropdown-Kandidaten aus dem Default-Workspace.
  useEffect(() => {
    if (locked !== false || workspaceId === null) {
      return
    }
    let cancelled = false
    createApi(authToken, workspaceId)
      .listAgents()
      .then((list) => {
        if (cancelled) return
        setAgents(list)
        if (list.length > 0) {
          setSelectedAgentId(list[0].id)
        }
      })
      .catch(() => {
        if (!cancelled) setError(t('connector.error'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [locked, workspaceId, authToken, t])

  const submit = useCallback(
    async (approve: boolean) => {
      if (requestBlob === '') {
        setError(t('connector.missingRequest'))
        return
      }
      setSubmitting(true)
      setError(null)
      try {
        const result = await oauthConsent(authToken, {
          request: requestBlob,
          agent_id: selectedAgentId,
          approve,
        })
        // Zurueck zum LLM-Client (mit `code`+`state` bzw. `error`). Voller
        // Page-Wechsel — das Ziel ist eine externe Client-Redirect-URI.
        window.location.assign(result.redirect)
      } catch {
        setError(t('connector.error'))
        setSubmitting(false)
      }
    },
    [authToken, requestBlob, selectedAgentId, t],
  )

  // Ohne Session keine Autorisierung — auf den Login, der via `next` zurueck
  // auf diese Consent-Seite (inkl. `?request=`) springt.
  if (session === null) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  // Approve ist nur zulaessig, wenn ein Agent tatsaechlich feststeht: im
  // Lock-Fall der aufgeloeste gelockte Agent, sonst die Dropdown-Auswahl.
  const canApprove = locked === true ? lockedAgent !== null : selectedAgentId !== ''

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('connector.title')}</CardTitle>
          <CardDescription>
            {clientName !== null
              ? t('connector.description', { client: clientName })
              : t('connector.descriptionGeneric')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            {error !== null ? <ErrorAlert message={error} /> : null}
            {requestBlob === '' ? (
              <ErrorAlert message={t('connector.missingRequest')} />
            ) : loading ? (
              <LoadingState rows={2} />
            ) : locked === null ? null : locked === false && agents.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('connector.noAgents')}</p>
            ) : (
              <>
                {locked === true ? (
                  lockedAgent !== null ? (
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="oauth-agent-locked">{t('connector.lockedLabel')}</Label>
                      <Input id="oauth-agent-locked" readOnly value={lockedAgent.name} />
                      <p className="text-xs text-muted-foreground">
                        {t('connector.lockedWorkspace', { workspace: lockedAgent.workspace_name })}
                      </p>
                      <p className="text-xs text-muted-foreground">{t('connector.lockedHint')}</p>
                    </div>
                  ) : (
                    <ErrorAlert message={t('connector.lockedUnresolvable')} />
                  )
                ) : (
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="oauth-agent">{t('connector.agentLabel')}</Label>
                    <Select
                      id="oauth-agent"
                      value={selectedAgentId}
                      onChange={(event) => setSelectedAgentId(event.target.value)}
                      disabled={submitting}
                    >
                      {agents.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </Select>
                    <p className="text-xs text-muted-foreground">{t('connector.agentHint')}</p>
                  </div>
                )}
                {redirectHost !== null ? (
                  <p className="text-xs text-muted-foreground">
                    {t('connector.redirectTo')}{' '}
                    <span className="font-medium text-foreground">{redirectHost}</span>
                  </p>
                ) : null}
                <div className="flex flex-col gap-2">
                  <Button
                    type="button"
                    variant="brand"
                    className="w-full"
                    onClick={() => void submit(true)}
                    disabled={submitting || !canApprove}
                  >
                    <Link2 className="h-4 w-4" />
                    {t('connector.approve')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => void submit(false)}
                    disabled={submitting}
                  >
                    {t('connector.deny')}
                  </Button>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}

interface BlobInfo {
  clientName: string | null
  redirectHost: string | null
}

// Liest `client_name` + `redirect_uri` aus dem signierten Request-Blob
// (base64url(JSON).sig) — die Signaturpruefung passiert serverseitig. Der
// `client_name` ist vom Client frei waehlbar (KEIN Vertrauensanker); die
// `redirect_uri` ist HMAC-signiert und damit der verlaessliche Anker dafuer,
// WOHIN autorisiert wird. Beides ist reine UI-Vorschau (Microcopy) — nichts
// davon steuert mehr, ob/welcher Agent gesperrt ist: das entscheidet
// ausschliesslich `POST /oauth/consent/preview` (siehe oben), nicht mehr ein
// clientseitig aus dem Blob gelesenes `agent_id`. Parse-Fehler ⇒ generisch
// (kein Crash) — der Blob geht trotzdem unveraendert an die Preview/den
// Consent, deren Signaturpruefung entscheidet ueber Gueltigkeit.
function readBlobInfo(blob: string): BlobInfo {
  if (blob === '') return { clientName: null, redirectHost: null }
  try {
    const body = blob.split('.')[0]
    const json = atob(body.replace(/-/g, '+').replace(/_/g, '/'))
    const parsed = JSON.parse(json) as {
      client_name?: unknown
      redirect_uri?: unknown
    }
    const clientName =
      typeof parsed.client_name === 'string' && parsed.client_name !== ''
        ? parsed.client_name
        : null
    let redirectHost: string | null = null
    if (typeof parsed.redirect_uri === 'string' && parsed.redirect_uri !== '') {
      try {
        redirectHost = new URL(parsed.redirect_uri).host
      } catch {
        redirectHost = null
      }
    }
    return { clientName, redirectHost }
  } catch {
    return { clientName: null, redirectHost: null }
  }
}
