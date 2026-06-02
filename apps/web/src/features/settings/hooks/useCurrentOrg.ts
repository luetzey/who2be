import type { MeOrganization, MeWorkspaceMembership } from '@/api/types'
import { useSession } from '@/auth/session-context'
import { useWorkspaceId } from '@/auth/useWorkspaceId'

export interface CurrentOrgContext {
  org: MeOrganization
  workspace: MeWorkspaceMembership
}

// Loest die Organization auf, zu der der aktive Workspace gehoert — Quelle ist
// der `/v1/me`-Snapshot (kein zusaetzlicher Fetch). `null`, solange `me` fehlt
// oder der Workspace (noch) nicht in einer Membership auftaucht.
export function useCurrentOrg(): CurrentOrgContext | null {
  const { me } = useSession()
  const workspaceId = useWorkspaceId()
  if (me === null || workspaceId === '') {
    return null
  }
  for (const org of me.organizations) {
    const workspace = org.workspaces.find((ws) => ws.id === workspaceId)
    if (workspace !== undefined) {
      return { org, workspace }
    }
  }
  return null
}
