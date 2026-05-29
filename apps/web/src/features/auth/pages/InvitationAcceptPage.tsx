import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useLocation, useParams } from 'react-router-dom'

import { acceptInvitation, ApiError } from '@/api/client'
import { useAuthToken } from '@/auth/useAuthToken'
import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'

// Microcopy beantwortet das WIESO (design-language §1): warum der Link nicht
// (mehr) funktioniert.
function messageForError(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 410) {
      return 'Diese Einladung ist abgelaufen. Bitte fordere eine neue an.'
    }
    if (cause.status === 404) {
      return 'Diese Einladung existiert nicht oder wurde bereits eingelöst.'
    }
  }
  return cause instanceof Error ? cause.message : 'Einladung konnte nicht angenommen werden.'
}

export function InvitationAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const { session } = useSession()
  const authToken = useAuthToken()
  const location = useLocation()

  const [accepting, setAccepting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [acceptedWorkspace, setAcceptedWorkspace] = useState<string | null>(null)

  // Ohne Session geht die Annahme nicht — zurück zum Login, der via `next`
  // wieder hierher zurückspringt.
  if (session === null) {
    const next = encodeURIComponent(location.pathname)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  if (acceptedWorkspace !== null) {
    return <Navigate to={`/w/${acceptedWorkspace}/dashboard`} replace />
  }

  if (token === undefined || token === '') {
    return <Navigate to="/" replace />
  }

  async function onAccept() {
    if (token === undefined) {
      return
    }
    setAccepting(true)
    setError(null)
    try {
      const result = await acceptInvitation(authToken, token)
      notify.success('Einladung angenommen.')
      setAcceptedWorkspace(result.workspace_id)
    } catch (cause) {
      setError(messageForError(cause))
    } finally {
      setAccepting(false)
    }
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
            Tritt dem Workspace bei, zu dem du eingeladen wurdest.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            {error !== null ? <ErrorAlert message={error} /> : null}
            <Button
              type="button"
              variant="brand"
              className="w-full"
              onClick={() => void onAccept()}
              disabled={accepting}
            >
              <MailCheck className="h-4 w-4" />
              Einladung annehmen
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
