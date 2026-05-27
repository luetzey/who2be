import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { Toaster } from '@/components/ui/sonner'
import { useSession } from '@/auth/session-context'

import { RouteErrorBoundary } from './RouteErrorBoundary'
import { RouteFallback } from './RouteFallback'
import { ThemeProvider } from './ThemeProvider'

export function AppLayout() {
  const { signOut } = useSession()
  return (
    <ThemeProvider>
      <AppShell onSignOut={() => void signOut()}>
        <RouteErrorBoundary>
          <Suspense fallback={<RouteFallback />}>
            <Outlet />
          </Suspense>
        </RouteErrorBoundary>
      </AppShell>
      <Toaster richColors closeButton position="bottom-right" />
    </ThemeProvider>
  )
}
