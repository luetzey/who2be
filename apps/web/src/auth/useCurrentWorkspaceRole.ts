import type { WorkspaceRole } from '@/api/types'

import { useSession } from './session-context'
import { useWorkspaceId } from './useWorkspaceId'

// Rolle des eingeloggten Users im aktiven Workspace. Quelle ist der bereits
// nach Login geladene `/v1/me`-Snapshot (Memberships pro Workspace) — kein
// zusaetzlicher Fetch noetig. `null`, solange `me` fehlt, kein Workspace
// resolved werden konnte oder der User dort kein Mitglied ist. Konsumenten
// behandeln `null` konservativ (kein Admin, aber auch kein harter Lock-out —
// das Backend enforced zusaetzlich).
export function useCurrentWorkspaceRole(): WorkspaceRole | null {
  const { me } = useSession()
  const workspaceId = useWorkspaceId()
  if (me === null || workspaceId === '') {
    return null
  }
  for (const org of me.organizations) {
    const membership = org.workspaces.find((ws) => ws.id === workspaceId)
    if (membership !== undefined) {
      return membership.role
    }
  }
  return null
}
