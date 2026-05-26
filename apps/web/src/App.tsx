import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthTokenProvider } from './auth/AuthTokenProvider'
import { RequireAuth } from './auth/RequireAuth'
import { SessionProvider } from './auth/SessionProvider'
import { LoginPage } from './features/auth'
import { PersonaDetailPage } from './pages/PersonaDetailPage'
import { PersonaNewPage } from './pages/PersonaNewPage'
import { PersonasPage } from './features/personas'
import { PlaybookDetailPage } from './pages/PlaybookDetailPage'
import { PlaybookNewPage } from './pages/PlaybookNewPage'
import { PlaybooksPage } from './pages/PlaybooksPage'
import { SettingsTokensPage } from './pages/SettingsTokensPage'

export function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <AuthTokenProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<PersonasPage />} />
              <Route path="/personas/new" element={<PersonaNewPage />} />
              <Route path="/personas/:id" element={<PersonaDetailPage />} />
              <Route path="/playbooks" element={<PlaybooksPage />} />
              <Route path="/playbooks/new" element={<PlaybookNewPage />} />
              <Route path="/playbooks/:id" element={<PlaybookDetailPage />} />
              <Route path="/settings/tokens" element={<SettingsTokensPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthTokenProvider>
      </SessionProvider>
    </BrowserRouter>
  )
}
