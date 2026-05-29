import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'

import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { RequireAuth } from '@/auth/RequireAuth'
import { SessionProvider } from '@/auth/SessionProvider'
import { useSession } from '@/auth/session-context'
import { InvitationAcceptPage, LoginPage, SetPasswordPage } from '@/features/auth'

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
const ResourcesPage = lazy(() =>
  import('@/features/resources/pages/ResourcesPage').then((mod) => ({
    default: mod.ResourcesPage,
  })),
)
const ResourceNewPage = lazy(() =>
  import('@/features/resources/pages/ResourceNewPage').then((mod) => ({
    default: mod.ResourceNewPage,
  })),
)
const ResourceDetailPage = lazy(() =>
  import('@/features/resources/pages/ResourceDetailPage').then((mod) => ({
    default: mod.ResourceDetailPage,
  })),
)
const SettingsTokensPage = lazy(() =>
  import('@/features/tokens/pages/SettingsTokensPage').then((mod) => ({
    default: mod.SettingsTokensPage,
  })),
)
const MembersPage = lazy(() =>
  import('@/features/settings/pages/MembersPage').then((mod) => ({
    default: mod.MembersPage,
  })),
)
const DashboardPage = lazy(() =>
  import('@/features/dashboard/pages/DashboardPage').then((mod) => ({
    default: mod.DashboardPage,
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

// Default-Redirect nach Login: hebt den User auf `/w/{default_workspace_id}/dashboard`.
// `me` kommt aus `/v1/me`, das der SessionProvider nach Sign-In laedt; falls noch
// nicht resolved, bleibt der User auf Login zurueckgeworfen.
function DefaultWorkspaceRedirect() {
  const { me } = useSession()
  const workspaceId = me?.default_workspace_id
  if (!workspaceId) {
    return <Navigate to="/login" replace />
  }
  return <Navigate to={`/w/${workspaceId}/dashboard`} replace />
}

// Index-Redirect unter `/w/:workspaceId` — laesst tiefe Bookmarks ohne
// Tail auf das Dashboard fallen.
function WorkspaceIndexRedirect() {
  const params = useParams<{ workspaceId: string }>()
  return <Navigate to={`/w/${params.workspaceId}/dashboard`} replace />
}

export function RouterRoot() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <AuthTokenProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/invitations/:token/accept"
              element={<InvitationAcceptPage />}
            />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<DefaultWorkspaceRedirect />} />
              <Route path="/onboarding/set-password" element={<SetPasswordPage />} />
              <Route element={<AppLayout />}>
                <Route path="/w/:workspaceId" element={<WorkspaceIndexRedirect />} />
                <Route path="/w/:workspaceId/dashboard" element={<DashboardPage />} />
                <Route path="/w/:workspaceId/personas" element={<PersonasPage />} />
                <Route path="/w/:workspaceId/personas/new" element={<PersonaNewPage />} />
                <Route path="/w/:workspaceId/personas/:id" element={<PersonaDetailPage />} />
                <Route path="/w/:workspaceId/playbooks" element={<PlaybooksPage />} />
                <Route path="/w/:workspaceId/playbooks/new" element={<PlaybookNewPage />} />
                <Route path="/w/:workspaceId/playbooks/:id" element={<PlaybookDetailPage />} />
                <Route path="/w/:workspaceId/resources" element={<ResourcesPage />} />
                <Route path="/w/:workspaceId/resources/new" element={<ResourceNewPage />} />
                <Route path="/w/:workspaceId/resources/:id" element={<ResourceDetailPage />} />
                <Route
                  path="/w/:workspaceId/settings/tokens"
                  element={<SettingsTokensPage />}
                />
                <Route
                  path="/w/:workspaceId/settings/members"
                  element={<MembersPage />}
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
