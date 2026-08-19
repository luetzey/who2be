import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { DeleteBlocker } from '@/api/types'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
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

export interface EntityDeleteButtonTexts {
  /** Dialog-Ueberschrift, z. B. "Persona löschen?" (entity-spezifisch, von der Seite uebersetzt). */
  dialogTitle: string
  /** Erfolgs-Toast nach dem Löschen, z. B. "Persona gelöscht." */
  success: string
  /** Tooltip-Text fuer Viewer (Trigger-Button ist dann disabled). */
  viewerReadOnly: string
  /** Praefix vor der Verwender-Liste im 409-Blocker-Alert, z. B. "Diese Persona wird noch verwendet von:" */
  blockedMessage: string
}

interface EntityDeleteButtonProps {
  /** Anzeigename der Entitaet fuer die Dialog-Beschreibung ({{name}}-Interpolation). */
  name: string
  texts: EntityDeleteButtonTexts
  /** Fuehrt den eigentlichen Lösch-Request aus; wirft bei Fehler (409 → Blocker-Anzeige). */
  onDelete: () => Promise<void>
  /** Pfad, zu dem nach erfolgreichem Löschen navigiert wird. */
  listPath: string
  /** Praefix fuer die `data-testid`-Werte (`${testIdPrefix}-trigger` / `${testIdPrefix}-confirm`). */
  testIdPrefix: string
}

/**
 * Generischer Hard-Delete-Button mit Bestaetigungsdialog fuer eine versionierte
 * Entitaet (Persona/Playbook/Resource/Tool). Navigiert bei Erfolg zur uebergebenen
 * Liste. Fuer Viewer deaktiviert (nur editor+, ADR-0023). Blockiert das Backend
 * mit 409, weil die Entitaet noch referenziert wird, werden die Verwender im
 * Dialog gelistet — kein blindes Retry.
 */
export function EntityDeleteButton({
  name,
  texts,
  onDelete,
  listPath,
  testIdPrefix,
}: EntityDeleteButtonProps) {
  const { t } = useTranslation('common')
  const navigate = useNavigate()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [blockers, setBlockers] = useState<DeleteBlocker[] | null>(null)

  const handleDelete = async () => {
    setBusy(true)
    setBlockers(null)
    try {
      await onDelete()
      notify.success(texts.success)
      navigate(listPath)
    } catch (cause: unknown) {
      const found = extractDeleteBlockers(cause)
      if (found.length > 0) {
        setBlockers(found)
      } else {
        notify.error(cause instanceof Error ? cause.message : t('entityDelete.error'))
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
          title={isViewer ? texts.viewerReadOnly : undefined}
          data-testid={`${testIdPrefix}-trigger`}
        >
          <Trash2 className="h-4 w-4" />
          {t('entityDelete.label')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{texts.dialogTitle}</DialogTitle>
          <DialogDescription>{t('entityDelete.dialogDescription', { name })}</DialogDescription>
        </DialogHeader>
        {blockers !== null ? (
          <ErrorAlert
            title={t('entityDelete.blockedTitle')}
            message={`${texts.blockedMessage} ${blockers
              .map(blockerLabel)
              .filter((label) => label !== '')
              .join(', ')}`.trim()}
          />
        ) : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={busy || blockers !== null}
            onClick={() => void handleDelete()}
            data-testid={`${testIdPrefix}-confirm`}
          >
            {t('entityDelete.confirmLabel')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
