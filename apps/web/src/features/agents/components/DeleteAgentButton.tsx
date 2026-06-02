import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { notify } from '@/lib/feedback'

interface DeleteAgentButtonProps {
  agent: Agent
}

/**
 * Loescht einen Agent nach Bestaetigung im Dialog und navigiert zurueck zur
 * Liste. Fuer Viewer deaktiviert (nur editor+ duerfen schreiben, ADR-0023).
 */
export function DeleteAgentButton({ agent }: DeleteAgentButtonProps) {
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const onDelete = async () => {
    setBusy(true)
    try {
      await api.deleteAgent(agent.id)
      notify.success('Agent gelöscht.')
      navigate(wsPath('/agents'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : 'Löschen fehlgeschlagen.')
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="destructive"
          disabled={isViewer}
          title={isViewer ? 'Viewer können Agents nur ansehen' : undefined}
          data-testid="delete-agent-trigger"
        >
          <Trash2 className="h-4 w-4" />
          Löschen
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Agent löschen?</DialogTitle>
          <DialogDescription>
            „{agent.name}" wird dauerhaft entfernt. Diese Aktion kann nicht rückgängig gemacht
            werden.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              Abbrechen
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={busy}
            onClick={() => void onDelete()}
            data-testid="delete-agent-confirm"
          >
            Endgültig löschen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
