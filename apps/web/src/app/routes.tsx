import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { RequireAuth } from '@/auth/RequireAuth'
import { SessionProvider } from '@/auth/SessionProvider'
import { useSession } from '@/auth/session-context'
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

// DEV-only Component-Catalog (ADR 0018). In Production-Builds wird die Route
// nicht registriert — Vite-Tree-Shaking laesst den Chunk dann komplett weg.
const CatalogPage = import.meta.env.DEV
  ? lazy(() =>
      import('./catalog/CatalogPage').then((mod) => ({
        default: mod.CatalogPage,
      })),
    )
  : null

// Default-Redirect nach Login: hebt den User auf `/w/{default_workspace_id}/personas`.
// `me` kommt aus `/v1/me`, das der SessionProvider nach Sign-In laedt; falls noch
// nicht resolved, bleibt der User auf Login zurueckgeworfen.
function DefaultWorkspaceRedirect() {
  const { me } = useSession()
  const workspaceId = me?.default_workspace_id
  if (!workspaceId) {
    return <Navigate to="/login" replace />
  }
  return <Navigate to={`/w/${workspaceId}/personas`} replace />
}

export function RouterRoot() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <AuthTokenProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<DefaultWorkspaceRedirect />} />
              <Route element={<AppLayout />}>
                <Route path="/w/:workspaceId/personas" element={<PersonasPage />} />
                <Route path="/w/:workspaceId/personas/new" element={<PersonaNewPage />} />
                <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
                <Route path="/w/:workspaceId/playbooks" element={<PlaybooksPage />} />
                <Route path="/w/:workspaceId/playbooks/new" element={<PlaybookNewPage />} />
                <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
                <Route
                  path="/w/:workspaceId/settings/tokens"
                  element={<SettingsTokensPage />}
                />
                {CatalogPage ? (
                  <Route path="/_catalog" element={<CatalogPage />} />
                ) : null}
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthTokenProvider>
      </SessionProvider>
    </BrowserRouter>
  )
}
