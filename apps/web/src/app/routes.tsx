import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { RequireAuth } from '@/auth/RequireAuth'
import { SessionProvider } from '@/auth/SessionProvider'
import { LoginPage } from '@/features/auth'

import { AppLayout } from './AppLayout'

// Eager: `LoginPage` ist die einzige Route ausserhalb `<AppLayout>`/`<Suspense>`
// und muss synchron verfuegbar sein. Die Authenticated-Routes liegen unter
// `AppLayout`s Suspense-Boundary — daher lazy mit eigenen Chunks pro Page.
const PersonasPage = lazy(() =>
  import('@/features/personas/pages/PersonasPage').then((mod) => ({
    default: mod.PersonasPage,
  })),
)
const PersonaNewPage = lazy(() =>
  import('@/features/personas/pages/PersonaNewPage').then((mod) => ({
    default: mod.PersonaNewPage,
  })),
)
const PersonaDetailPage = lazy(() =>
  import('@/features/personas/pages/PersonaDetailPage').then((mod) => ({
    default: mod.PersonaDetailPage,
  })),
)
const PlaybooksPage = lazy(() =>
  import('@/features/playbooks/pages/PlaybooksPage').then((mod) => ({
    default: mod.PlaybooksPage,
  })),
)
const PlaybookNewPage = lazy(() =>
  import('@/features/playbooks/pages/PlaybookNewPage').then((mod) => ({
    default: mod.PlaybookNewPage,
  })),
)
const PlaybookDetailPage = lazy(() =>
  import('@/features/playbooks/pages/PlaybookDetailPage').then((mod) => ({
    default: mod.PlaybookDetailPage,
  })),
)
const SettingsTokensPage = lazy(() =>
  import('@/features/tokens/pages/SettingsTokensPage').then((mod) => ({
    default: mod.SettingsTokensPage,
  })),
)

export function RouterRoot() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <AuthTokenProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<PersonasPage />} />
                <Route path="/personas/new" element={<PersonaNewPage />} />
                <Route path="/personas/:id" element={<PersonaDetailPage />} />
                <Route path="/playbooks" element={<PlaybooksPage />} />
                <Route path="/playbooks/new" element={<PlaybookNewPage />} />
                <Route path="/playbooks/:id" element={<PlaybookDetailPage />} />
                <Route path="/settings/tokens" element={<SettingsTokensPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthTokenProvider>
      </SessionProvider>
    </BrowserRouter>
  )
}
