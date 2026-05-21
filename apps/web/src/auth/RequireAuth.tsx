import { Navigate, Outlet } from 'react-router-dom'

import { useSession } from './session-context'

export function RequireAuth() {
  const { session } = useSession()
  if (session === null) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
