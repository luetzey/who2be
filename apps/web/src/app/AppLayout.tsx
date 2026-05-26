import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { useSession } from '@/auth/session-context'

import { RouteErrorBoundary } from './RouteErrorBoundary'
import { RouteFallback } from './RouteFallback'

export function AppLayout() {
  const { signOut } = useSession()
  return (
    <AppShell onSignOut={() => void signOut()}>
      <RouteErrorBoundary>
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </RouteErrorBoundary>
    </AppShell>
  )
}
