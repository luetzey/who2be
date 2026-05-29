import { MailCheck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { acceptInvitation, ApiError } from '@/api/client'
import { useAuthToken } from '@/auth/useAuthToken'
import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'

// Microcopy beantwortet das WIESO (design-language §1): warum der Link nicht
// (mehr) funktioniert. 403 ist neu (Phase 3-D Magic-Link-Email-Check).
function messageForError(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 410) {
      return 'Diese Einladung ist abgelaufen. Bitte fordere eine neue an.'
    }
    if (cause.status === 404) {
      return 'Diese Einladung existiert nicht oder wurde bereits eingelöst.'
    }
    if (cause.status === 403) {
      return 'Diese Einladung ist für eine andere Email-Adresse.'
    }
  }
  return cause instanceof Error ? cause.message : 'Einladung konnte nicht angenommen werden.'
}

export function InvitationAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const { session, me } = useSession()
  const authToken = useAuthToken()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  // `via=magic` markiert den GoTrue-Magic-Link-Callback: User ist nach dem
  // Mail-Klick bereits eingeloggt, die Page nimmt die Einladung automatisch
  // an. Manueller Aufruf ohne den Marker behaelt den klassischen
  // Button-Flow (Token wurde geteilt, der User entscheidet aktiv).
  const isMagicLink = searchParams.get('via') === 'magic'

  const [accepting, setAccepting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [acceptedWorkspace, setAcceptedWorkspace] = useState<string | null>(null)
  // Auto-Accept darf nur einmal feuern, auch bei React-StrictMode-Doppel-Mount.
  const autoAcceptedRef = useRef(false)

  async function runAccept(currentToken: string, currentAuthToken: string) {
    setAccepting(true)
    setError(null)
    try {
      const result = await acceptInvitation(currentAuthToken, currentToken)
      notify.success('Einladung angenommen.')
      setAcceptedWorkspace(result.workspace_id)
    } catch (cause) {
      setError(messageForError(cause))
    } finally {
      setAccepting(false)
    }
  }

  useEffect(() => {
    if (
      !isMagicLink
      || autoAcceptedRef.current
      || session === null
      || token === undefined
      || token === ''
    ) {
      return
    }
    autoAcceptedRef.current = true
    void runAccept(token, authToken)
  }, [isMagicLink, session, token, authToken])

  // Ohne Session geht die Annahme nicht — zurück zum Login, der via `next`
  // wieder hierher zurückspringt. Magic-Link-User sind nach dem GoTrue-Callback
  // immer eingeloggt; landet er trotzdem hier ohne Session, ist der Callback
  // schiefgegangen — Login-Redirect ist die richtige Recovery.
  if (session === null) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  // Frisch via Magic-Link eingeloggt, aber noch ohne Passwort: erst Passwort
  // setzen, dann zurueck zur Accept-Page (mit `via=magic`, damit Auto-Accept
  // wieder greift). Andernfalls bleibt der User in einer Sackgasse, sobald
  // der Magic-Link-Token einmal verbraucht ist.
  if (isMagicLink && me !== null && me.has_password === false) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/onboarding/set-password?next=${next}`} replace />
  }

  if (acceptedWorkspace !== null) {
    return <Navigate to={`/w/${acceptedWorkspace}/dashboard`} replace />
  }

  if (token === undefined || token === '') {
    return <Navigate to="/" replace />
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Who2Be
          </span>
          <CardTitle className="text-3xl tracking-tight">Einladung annehmen</CardTitle>
          <CardDescription>
            {isMagicLink
              ? 'Du wirst angemeldet…'
              : 'Tritt dem Workspace bei, zu dem du eingeladen wurdest.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            {error !== null ? <ErrorAlert message={error} /> : null}
            {isMagicLink ? null : (
              <Button
                type="button"
                variant="brand"
                className="w-full"
                onClick={() => void runAccept(token, authToken)}
                disabled={accepting}
              >
                <MailCheck className="h-4 w-4" />
                Einladung annehmen
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
