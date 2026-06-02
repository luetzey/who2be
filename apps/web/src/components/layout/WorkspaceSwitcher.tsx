import { Check, ChevronsUpDown, Plus } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import type { MeOrganization } from '@/api/types'
import { useSession } from '@/auth/session-context'
import { useWorkspaceId } from '@/auth/useWorkspaceId'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

const LAST_WORKSPACE_KEY = 'lastWorkspaceId'

interface ResolvedWorkspace {
  orgName: string
  wsName: string
}

function findCurrentLabel(
  organizations: MeOrganization[],
  workspaceId: string,
): ResolvedWorkspace | null {
  for (const org of organizations) {
    const ws = org.workspaces.find((entry) => entry.id === workspaceId)
    if (ws !== undefined) {
      return { orgName: org.name, wsName: ws.name }
    }
  }
  return null
}

// Zwei-Stufen-Workspace-Wechsler in der Sidebar (Phase 3-C, F-01). Lesen
// aus `useSession().me` — kein zusaetzlicher Fetch. Auswahl persistiert
// die letzte Workspace-Id in `localStorage` (Bookmarks-Fallback) und
// navigiert auf das Dashboard des neuen Workspace.
export function WorkspaceSwitcher() {
  const { me } = useSession()
  const navigate = useNavigate()
  const currentWorkspaceId = useWorkspaceId()
  const wsPath = useWorkspacePath()

  if (me === null || me.organizations.length === 0) {
    return null
  }

  const current = findCurrentLabel(me.organizations, currentWorkspaceId)
  const triggerLabel =
    current !== null ? current.wsName : 'Workspace wählen'
  const triggerSubLabel = current !== null ? current.orgName : 'Kein Workspace aktiv'

  const handleSelect = (workspaceId: string) => {
    if (workspaceId === currentWorkspaceId) {
      return
    }
    try {
      window.localStorage.setItem(LAST_WORKSPACE_KEY, workspaceId)
    } catch {
      // Storage kann in Privacy-Modi blockiert sein — fuer den Wechsel selbst irrelevant.
    }
    navigate(`/w/${workspaceId}/dashboard`)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex h-auto w-full items-center justify-between gap-2 px-2 py-2 text-left"
          aria-label="Workspace wechseln"
        >
          <span className="flex min-w-0 flex-col">
            <span className="truncate text-sm font-medium">{triggerLabel}</span>
            <span className="truncate text-xs text-muted-foreground">
              {triggerSubLabel}
            </span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-56">
        {me.organizations.map((org, orgIndex) => (
          <div key={org.id}>
            {orgIndex > 0 ? <DropdownMenuSeparator /> : null}
            <DropdownMenuLabel className="flex items-center justify-between gap-2">
              <span className="truncate">{org.name}</span>
              <span className="text-xs font-normal text-muted-foreground">
                {org.kind === 'personal' ? 'Persönlich' : 'Organisation'}
              </span>
            </DropdownMenuLabel>
            {org.workspaces.length === 0 ? (
              <DropdownMenuItem disabled>
                Keine Workspaces in dieser Organisation
              </DropdownMenuItem>
            ) : (
              org.workspaces.map((ws) => {
                const active = ws.id === currentWorkspaceId
                return (
                  <DropdownMenuItem
                    key={ws.id}
                    onSelect={() => handleSelect(ws.id)}
                    className={cn(active && 'bg-accent text-accent-foreground')}
                  >
                    <Check
                      className={cn(
                        'size-4 shrink-0',
                        active ? 'opacity-100' : 'opacity-0',
                      )}
                      aria-hidden="true"
                    />
                    <span className="truncate">{ws.name}</span>
                  </DropdownMenuItem>
                )
              })
            )}
          </div>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to={wsPath('/settings/org')} className="flex items-center gap-2">
            <Plus className="size-4" aria-hidden="true" />
            Workspace anlegen
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
