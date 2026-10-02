import { MailCheck } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { acceptPendingInvitation, ApiError, listPendingInvitations } from '@/api/client'
import type { PendingInvitation } from '@/api/types'
import { useAuthToken } from '@/auth/useAuthToken'
import { useSession } from '@/auth/session-context'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'
import { roleLabel } from '@/lib/roles'

/** Eigene Adresse — Ziel des tokenlosen Mail-Links und jedes Ruecksprungs. */
const PAGE_PATH = '/invitations'

const EMAIL_REASONS = new Set(['invitation_email_required', 'invitation_email_unconfirmed'])

function reasonOf(cause: ApiError): string | null {
  const body = cause.body
  if (body !== null && typeof body === 'object' && 'reason' in body) {
    const reason = (body as { reason: unknown }).reason
    return typeof reason === 'string' ? reason : null
  }
  return null
}

interface PageError {
  /** Fehlende bzw. unbestaetigte Konto-Adresse: der Nutzer muss erst bestaetigen. */
  email: boolean
  message: string
}

type ListState =
  | { kind: 'loading' }
  | { kind: 'ready'; items: PendingInvitation[] }
  | { kind: 'failed'; error: PageError }

/**
 * Offene Einladungen an die E-Mail-Adresse des eingeloggten Kontos (S2b W3).
 *
 * Ziel des Links aus der Einladungsmail: der Link traegt keinen Token, die
 * Seite fragt nach dem Login `GET /v1/invitations/pending` und nimmt eine
 * Einladung per Klick ueber ihre ID an. Der Token-Weg fuer manuell geteilte
 * Links bleibt `InvitationAcceptPage` (`/invitations/accept#token=…`).
 *
 * Ohne Session faengt `RequireAuth` ab und schickt mit `next=/invitations`
 * zum Login. Neukonten aus dem GoTrue-Invite kommen mit der Session im
 * URL-Hash an (`SessionProvider` uebernimmt sie) und setzen zuerst ein
 * Passwort, bevor es hier weitergeht.
 */
export function PendingInvitationsPage() {
  const { t } = useTranslation('auth')
  const { session, me, refreshMe } = useSession()
  const authToken = useAuthToken()
  const navigate = useNavigate()
  const [state, setState] = useState<ListState>({ kind: 'loading' })
  const [acceptingId, setAcceptingId] = useState<string | null>(null)
  const [acceptError, setAcceptError] = useState<PageError | null>(null)

  // Microcopy beantwortet das WIESO (design-language §1).
  const errorFor = useCallback(
    (cause: unknown): PageError => {
      if (cause instanceof ApiError) {
        if (cause.status === 403) {
          const reason = reasonOf(cause)
          if (reason !== null && EMAIL_REASONS.has(reason)) {
            return {
              email: true,
              message:
                reason === 'invitation_email_required'
                  ? t('common:errors.invitation_email_required')
                  : t('common:errors.invitation_email_unconfirmed'),
            }
          }
        }
        if (cause.status === 410) {
          return { email: false, message: t('invitation.error.expired') }
        }
        if (cause.status === 404) {
          return { email: false, message: t('invitation.error.notFound') }
        }
      }
      return {
        email: false,
        message: cause instanceof Error ? cause.message : t('invitation.error.generic'),
      }
    },
    [t],
  )

  // Laedt die Liste; setzt den Zustand erst nach der Antwort (kein
  // synchrones setState im Effect). `reload` zeigt vorher wieder „Laden“.
  const fetchList = useCallback(async () => {
    try {
      const items = await listPendingInvitations(authToken)
      setState({ kind: 'ready', items })
    } catch (cause) {
      setState({ kind: 'failed', error: errorFor(cause) })
    }
  }, [authToken, errorFor])

  const reload = useCallback(() => {
    setState({ kind: 'loading' })
    void fetchList()
  }, [fetchList])

  // Neukonto aus der Einladungsmail: GoTrue hat das Konto per Invite angelegt,
  // ein Passwort gibt es noch nicht. Erst setzen lassen, sonst fuehrt nach
  // dem Verbrauch des Mail-Links kein Weg mehr zurueck ins Konto.
  //
  // `me` wird vorher einmal frisch geholt: nach dem Passwort-Setzen kehrt der
  // Nutzer hierher zurueck, waehrend der Snapshot noch `has_password=false`
  // traegt — ohne Re-Fetch ginge es im Kreis zurueck auf die Passwort-Seite.
  const invitedWithoutPassword =
    me !== null && me.has_password === false && Boolean(session?.user?.invited_at)
  const [meRefreshed, setMeRefreshed] = useState(false)
  const refreshStartedRef = useRef(false)
  const meFresh = me !== null && (!invitedWithoutPassword || meRefreshed)
  const needsPassword = meFresh && invitedWithoutPassword

  useEffect(() => {
    if (!invitedWithoutPassword || refreshStartedRef.current) {
      return
    }
    refreshStartedRef.current = true
    void refreshMe().then(() => setMeRefreshed(true))
  }, [invitedWithoutPassword, refreshMe])

  const loadStartedRef = useRef(false)
  useEffect(() => {
    if (!meFresh || needsPassword || authToken === '' || loadStartedRef.current) {
      return
    }
    loadStartedRef.current = true
    void fetchList()
  }, [meFresh, needsPassword, authToken, fetchList])

  async function accept(invitation: PendingInvitation) {
    setAcceptingId(invitation.id)
    setAcceptError(null)
    try {
      const result = await acceptPendingInvitation(authToken, invitation.id)
      notify.success(t('invitation.success'))
      // `/v1/me` kennt die neue Mitgliedschaft erst nach einem Re-Fetch —
      // sonst fehlt der Workspace im Umschalter.
      await refreshMe()
      navigate(`/w/${result.workspace_id}/dashboard`, { replace: true })
    } catch (cause) {
      setAcceptError(errorFor(cause))
      setAcceptingId(null)
      // Abgelaufen oder nicht (mehr) vorhanden: die Liste ist veraltet.
      if (cause instanceof ApiError && (cause.status === 404 || cause.status === 410)) {
        reload()
      }
    }
  }

  if (needsPassword) {
    const next = encodeURIComponent(PAGE_PATH)
    return <Navigate to={`/onboarding/set-password?next=${next}`} replace />
  }

  let body: ReactNode
  if (!meFresh || state.kind === 'loading') {
    body = <LoadingState rows={2} />
  } else if (state.kind === 'failed') {
    body = (
      <ErrorAlert
        title={state.error.email ? t('pendingInvitations.emailTitle') : undefined}
        message={state.error.message}
      />
    )
  } else if (state.items.length === 0) {
    body = (
      <EmptyState
        icon={MailCheck}
        title={t('pendingInvitations.emptyTitle')}
        description={t('pendingInvitations.emptyDescription')}
        action={
          <Button asChild variant="outline">
            <Link to="/">{t('pendingInvitations.continue')}</Link>
          </Button>
        }
      />
    )
  } else {
    body = (
      <ul className="flex flex-col gap-3" aria-label={t('pendingInvitations.listLabel')}>
        {state.items.map((invitation) => {
          const busy = acceptingId === invitation.id
          return (
            <li
              key={invitation.id}
              className="flex flex-col gap-3 rounded-lg border p-4"
              data-testid="pending-invitation"
            >
              <div className="min-w-0 space-y-1">
                <p className="font-medium break-all">{invitation.workspace_name}</p>
                <p className="text-sm text-muted-foreground">
                  {t('pendingInvitations.role', { role: roleLabel(invitation.role) })}
                  {' · '}
                  {t('pendingInvitations.expires', {
                    date: new Date(invitation.expires_at).toLocaleDateString(),
                  })}
                </p>
              </div>
              <Button
                type="button"
                variant="brand"
                className="w-full"
                onClick={() => void accept(invitation)}
                disabled={acceptingId !== null}
                aria-label={t('pendingInvitations.acceptFor', {
                  workspace: invitation.workspace_name,
                })}
              >
                <MailCheck className="h-4 w-4" />
                {busy ? t('pendingInvitations.accepting') : t('invitation.submit')}
              </Button>
            </li>
          )
        })}
      </ul>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10 break-words">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('pendingInvitations.title')}</CardTitle>
          <CardDescription>{t('pendingInvitations.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            {acceptError !== null ? (
              <ErrorAlert
                title={acceptError.email ? t('pendingInvitations.emailTitle') : undefined}
                message={acceptError.message}
              />
            ) : null}
            {body}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
