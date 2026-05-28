import { useParams } from 'react-router-dom'

import { useSession } from './session-context'

// Liefert die aktive Workspace-ID fuer API-Calls. Vorrang: Route-Param
// `:workspaceId` (URL ist die Single-Source-of-Truth fuer den Tenant-Kontext);
// Fallback: `default_workspace_id` aus `/v1/me`. Leerer String, wenn nichts
// resolved werden konnte — die API-Calls schlagen dann sauber mit 403/404 fehl.
export function useWorkspaceId(): string {
  const params = useParams<{ workspaceId?: string }>()
  const { me } = useSession()
  if (params.workspaceId !== undefined && params.workspaceId !== '') {
    return params.workspaceId
  }
  return me?.default_workspace_id ?? ''
}
