import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { DeleteBlocker, Persona } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ErrorAlert } from '@/components/data/ErrorAlert'
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
import { blockerLabel, extractDeleteBlockers } from '@/lib/deleteBlockers'
import { notify } from '@/lib/feedback'

interface DeletePersonaButtonProps {
  persona: Persona
}

/**
 * Hard-Delete einer Persona nach Bestaetigung im Dialog, navigiert zurueck zur
 * Liste. Fuer Viewer deaktiviert (nur editor+, ADR-0023). Wird die Persona noch
 * referenziert, blockiert das Backend mit 409 — die Verwender werden dann im
 * Dialog gelistet, kein blindes Retry.
 */
export function DeletePersonaButton({ persona }: DeletePersonaButtonProps) {
  const { t } = useTranslation('personas')
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [blockers, setBlockers] = useState<DeleteBlocker[] | null>(null)

  const onDelete = async () => {
    setBusy(true)
    setBlockers(null)
    try {
      await api.deletePersona(persona.id)
      notify.success(t('delete.success'))
      navigate(wsPath('/personas'))
    } catch (cause: unknown) {
      const found = extractDeleteBlockers(cause)
      if (found.length > 0) {
        setBlockers(found)
      } else {
        notify.error(cause instanceof Error ? cause.message : t('delete.error'))
      }
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) {
          setBlockers(null)
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="destructive"
          disabled={isViewer}
          title={isViewer ? t('delete.viewerReadOnly') : undefined}
          data-testid="delete-persona-trigger"
        >
          <Trash2 className="h-4 w-4" />
          {t('delete.label')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('delete.dialogTitle')}</DialogTitle>
          <DialogDescription>
            {t('delete.dialogDescription', { name: persona.name })}
          </DialogDescription>
        </DialogHeader>
        {blockers !== null ? (
          <ErrorAlert
            title={t('delete.blockedTitle')}
            message={`${t('delete.blockedMessage')} ${blockers
              .map(blockerLabel)
              .filter((label) => label !== '')
              .join(', ')}`.trim()}
          />
        ) : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={busy || blockers !== null}
            onClick={() => void onDelete()}
            data-testid="delete-persona-confirm"
          >
            {t('delete.confirmLabel')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
