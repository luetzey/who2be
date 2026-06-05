import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState } from '@/components/data/LoadingState'

import { sanitizeNext } from '../lib/sanitize-next'

// Liest GoTrue-Fehler aus dem URL-Hash (`#error=…&error_description=…`).
// Erfolgreiche OAuth-/Confirm-Callbacks tragen stattdessen Tokens im Hash,
// die `detectSessionInUrl` im supabase-Client bereits konsumiert hat — die
// etablierte Session sehen wir dann ueber `useSession`.
function readHashError(): string | null {
  const hash = window.location.hash.startsWith('#')
    ? window.location.hash.slice(1)
    : window.location.hash
  if (hash === '') {
    return null
  }
  const params = new URLSearchParams(hash)
  const description = params.get('error_description')
  if (description !== null && description !== '') {
    return description.replace(/\+/g, ' ')
  }
  return params.get('error')
}

// Callback-Landing fuer Social-Login und E-Mail-Confirm (Track K). GoTrue
// schickt den Browser nach dem externen Login bzw. Mail-Klick hierher;
// `SessionProvider` parst die Hash-Tokens und etabliert die Session. Sobald
// sie steht, leiten wir auf den (gehaerteten) `next`-Pfad weiter; bleibt sie
// aus oder kommt ein Fehler im Hash, fuehren wir zurueck zum Login.
export function AuthCallbackPage() {
  const { t } = useTranslation('auth')
  const { session } = useSession()
  const [searchParams] = useSearchParams()
  const [hashError] = useState<string | null>(() => readHashError())
  const [timedOut, setTimedOut] = useState(false)

  const next = sanitizeNext(searchParams.get('next'))

  useEffect(() => {
    if (session !== null || hashError !== null) {
      return
    }
    // Fallback: etabliert sich nach ein paar Sekunden keine Session und kam
    // auch kein Fehler-Hash, ist der Callback ins Leere gelaufen (z. B. Hash
    // schon konsumiert/Reload) — zurueck zum Login statt Endlos-Spinner.
    const timer = setTimeout(() => setTimedOut(true), 4000)
    return () => clearTimeout(timer)
  }, [session, hashError])

  if (session !== null) {
    return <Navigate to={next} replace />
  }

  if (hashError !== null || timedOut) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
        <Card className="w-full max-w-md border-transparent shadow-modal">
          <CardHeader className="gap-2">
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t('brand')}
            </span>
            <CardTitle className="text-3xl tracking-tight">{t('callback.errorTitle')}</CardTitle>
            <CardDescription>{t('callback.errorDescription')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              <ErrorAlert
                message={hashError ?? t('callback.noSession')}
              />
              <Button asChild variant="brand" className="w-full">
                <Link to="/login">{t('backToLogin')}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('callback.loadingTitle')}</CardTitle>
          <CardDescription>{t('callback.loadingDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <LoadingState rows={2} />
        </CardContent>
      </Card>
    </main>
  )
}
