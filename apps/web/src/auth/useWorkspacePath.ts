import { useWorkspaceId } from './useWorkspaceId'

// Praefix-Helper fuer Workspace-scoped Routen.
// `wsPath('/personas/new')` -> `/w/{workspaceId}/personas/new`.
// Konsistent mit `useApi`: derselbe Workspace-Kontext fuer Daten + Navigation.
export function useWorkspacePath(): (relative: string) => string {
  const workspaceId = useWorkspaceId()
  return (relative: string) => {
    const path = relative.startsWith('/') ? relative : `/${relative}`
    return `/w/${workspaceId}${path}`
  }
}
