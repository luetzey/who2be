import { useTranslation } from 'react-i18next'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useSession } from './session-context'

export function RequireAuth() {
  const { t } = useTranslation('common')
  const { session, sessionLoaded } = useSession()
  const location = useLocation()

  // Session-Bootstrap laeuft noch: `session === null` heisst hier nur "noch
  // unbekannt". Ein Redirect jetzt wuerde die aktuelle URL wegwerfen und den
  // User nach dem Bootstrap immer auf dem Dashboard abladen (Reload-Bug).
  if (!sessionLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        {t('loadingLong')}
      </div>
    )
  }

  if (session === null) {
    // Ziel-URL als `next` mitgeben, damit der Login danach hierher
    // zurueckfuehrt statt auf das Default-Dashboard.
    const next = `${location.pathname}${location.search}`
    const to = next === '/' ? '/login' : `/login?next=${encodeURIComponent(next)}`
    return <Navigate to={to} replace />
  }

  return <Outlet />
}
