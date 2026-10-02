import { MailCheck } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { acceptInvitation, ApiError } from '@/api/client'
import { useAuthToken } from '@/auth/useAuthToken'
import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'

/** Tokenfreie Adresse der Seite — Ziel jedes Ruecksprungs (`next`). */
const ACCEPT_PATH = '/invitations/accept'

// Der Token ueberlebt Login, Passwort-Setzen und den Ruecksprung im
// sessionStorage (Tab-Lifetime) statt in einer URL: alles, was in Pfad oder
// Query steht, landet in Access-Logs, Verlauf und Referrer.
const STORAGE_KEY = 'who2be.invitationToken'

function readStoredToken(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function storeToken(token: string): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, token)
  } catch {
    // Ohne sessionStorage geht der Token nur ueber einen Login-Umweg
    // verloren; im selben Seitenaufruf bleibt er im State erhalten.
  }
}

function clearStoredToken(): void {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // siehe storeToken
  }
}

/** `#token=…` aus dem Fragment des geteilten Links; sonst `null`. */
function tokenFromHash(hash: string): string | null {
  const value = new URLSearchParams(hash.replace(/^#/, '')).get('token')
  return value === null || value === '' ? null : value
}

const EMAIL_REASONS = new Set(['invitation_email_required', 'invitation_email_unconfirmed'])

function reasonOf(cause: ApiError): string | null {
  const body = cause.body
  if (body !== null && typeof body === 'object' && 'reason' in body) {
    const reason = (body as { reason: unknown }).reason
    return typeof reason === 'string' ? reason : null
  }
  return null
}

export function InvitationAcceptPage() {
  const { t } = useTranslation('auth')
  // Legacy-Route `/invitations/:token/accept` fuer bereits verschickte Links;
  // der neue geteilte Link traegt den Token im Fragment (`#token=…`).
  const { token: pathToken } = useParams<{ token: string }>()
  const { session, me } = useSession()
  const authToken = useAuthToken()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  // `via=magic` markiert den GoTrue-Magic-Link-Callback: User ist nach dem
  // Mail-Klick bereits eingeloggt, die Page nimmt die Einladung automatisch
  // an. Manueller Aufruf ohne den Marker behaelt den klassischen
  // Button-Flow (Token wurde geteilt, der User entscheidet aktiv).
  const isMagicLink = searchParams.get('via') === 'magic'

  const hashToken = tokenFromHash(location.hash)
  const urlToken = hashToken ?? (pathToken !== undefined && pathToken !== '' ? pathToken : null)
  // Token aus der Adresse sofort beim Rendern sichern — noch bevor einer der
  // Redirects unten (Login, Passwort setzen) die Adresse verlaesst. Idempotent,
  // daher auch unter StrictMode-Doppel-Render unkritisch.
  if (urlToken !== null) {
    storeToken(urlToken)
  }
  // Pro Mount im State: nach dem Aufraeumen der Adresse (oder nach einem
  // 404/410, der den Speicher leert) bleibt der Token fuer diese Seite erhalten.
  const [token, setToken] = useState<string | null>(() => urlToken ?? readStoredToken())
  if (urlToken !== null && urlToken !== token) {
    setToken(urlToken)
  }

  const [accepting, setAccepting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [acceptedWorkspace, setAcceptedWorkspace] = useState<string | null>(null)
  // Auto-Accept darf nur einmal feuern, auch bei React-StrictMode-Doppel-Mount.
  const autoAcceptedRef = useRef(false)

  // Microcopy beantwortet das WIESO (design-language §1): warum der Link nicht
  // (mehr) funktioniert. 403 ist neu (Phase 3-D Magic-Link-Email-Check).
  const messageForError = useCallback(
    (cause: unknown): string => {
      if (cause instanceof ApiError) {
        if (cause.status === 410) {
          return t('invitation.error.expired')
        }
        if (cause.status === 404) {
          return t('invitation.error.notFound')
        }
        if (cause.status === 403) {
          // Fehlende bzw. unbestaetigte Konto-Adresse ist ein anderes Problem
          // als die falsche Adresse — der Nutzer muss etwas anderes tun.
          const reason = reasonOf(cause)
          if (reason !== null && EMAIL_REASONS.has(reason)) {
            return reason === 'invitation_email_required'
              ? t('common:errors.invitation_email_required')
              : t('common:errors.invitation_email_unconfirmed')
          }
          return t('invitation.error.emailMismatch')
        }
      }
      return cause instanceof Error ? cause.message : t('invitation.error.generic')
    },
    [t],
  )

  const runAccept = useCallback(
    async (currentToken: string, currentAuthToken: string) => {
      setAccepting(true)
      setError(null)
      try {
        const result = await acceptInvitation(currentAuthToken, currentToken)
        clearStoredToken()
        notify.success(t('invitation.success'))
        setAcceptedWorkspace(result.workspace_id)
      } catch (cause) {
        // Verbrauchter oder unbekannter Token wird nie mehr gueltig.
        if (cause instanceof ApiError && (cause.status === 404 || cause.status === 410)) {
          clearStoredToken()
        }
        setError(messageForError(cause))
      } finally {
        setAccepting(false)
      }
    },
    [t, messageForError],
  )

  const addressCarriesToken = urlToken !== null

  useEffect(() => {
    if (
      !isMagicLink
      || autoAcceptedRef.current
      || session === null
      || me === null
      || addressCarriesToken
      || token === null
    ) {
      return
    }
    autoAcceptedRef.current = true
    void runAccept(token, authToken)
  }, [isMagicLink, session, me, addressCarriesToken, token, authToken, runAccept])

  // Ruecksprung-Ziel ohne Token: der Token liegt im sessionStorage.
  const tokenFreeTarget = `${ACCEPT_PATH}${location.search}`

  // Ohne Session geht die Annahme nicht — zurück zum Login, der via `next`
  // wieder hierher zurückspringt. Magic-Link-User sind nach dem GoTrue-Callback
  // immer eingeloggt; landet er trotzdem hier ohne Session, ist der Callback
  // schiefgegangen — Login-Redirect ist die richtige Recovery.
  if (session === null) {
    const next = encodeURIComponent(tokenFreeTarget)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  // Token aus der Adresszeile nehmen (replace = `history.replaceState`), damit
  // er weder im Verlauf noch im Referrer stehen bleibt. Ein anderes Fragment
  // (z. B. die GoTrue-Session `#access_token=…`) bleibt erhalten.
  if (addressCarriesToken) {
    const keepHash = hashToken === null ? location.hash : ''
    return <Navigate to={`${tokenFreeTarget}${keepHash}`} replace />
  }

  // Session ist da, aber `/v1/me` ist noch unterwegs — das passiert beim
  // Magic-Link-Hash, der eine Session synchron etabliert, waehrend
  // `fetchMe` parallel laeuft. Ohne diesen Branch wuerde der Auto-Accept
  // ohne `has_password`-Wissen feuern und die Set-Password-Weiche bliebe
  // unklar; Login-Redirect ist hier falsch, weil die Session existiert.
  if (me === null) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10 break-words">
        <Card className="w-full max-w-md border-transparent shadow-modal">
          <CardHeader className="gap-2">
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t('brand')}
            </span>
            <CardTitle className="text-3xl tracking-tight">{t('invitation.title')}</CardTitle>
            <CardDescription>{t('invitation.loginPending')}</CardDescription>
          </CardHeader>
          <CardContent>
            <LoadingState rows={2} />
          </CardContent>
        </Card>
      </main>
    )
  }

  // Frisch via Magic-Link eingeloggt, aber noch ohne Passwort: erst Passwort
  // setzen, dann zurueck zur Accept-Page (mit `via=magic`, damit Auto-Accept
  // wieder greift). Andernfalls bleibt der User in einer Sackgasse, sobald
  // der Magic-Link-Token einmal verbraucht ist.
  if (isMagicLink && me.has_password === false) {
    const next = encodeURIComponent(tokenFreeTarget)
    return <Navigate to={`/onboarding/set-password?next=${next}`} replace />
  }

  if (acceptedWorkspace !== null) {
    return <Navigate to={`/w/${acceptedWorkspace}/dashboard`} replace />
  }

  if (token === null) {
    return <Navigate to="/" replace />
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10 break-words">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('invitation.title')}</CardTitle>
          <CardDescription>
            {isMagicLink
              ? t('invitation.descriptionMagic')
              : t('invitation.descriptionManual')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            {error !== null ? <ErrorAlert message={error} /> : null}
            {isMagicLink ? null : (
              <Button
                type="button"
                data-testid="invitation-accept-submit"
                variant="brand"
                className="w-full"
                onClick={() => void runAccept(token, authToken)}
                disabled={accepting}
              >
                <MailCheck className="h-4 w-4" />
                {t('invitation.submit')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
