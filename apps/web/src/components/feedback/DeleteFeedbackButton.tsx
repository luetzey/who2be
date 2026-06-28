import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

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

interface DeleteFeedbackButtonProps {
  /** Element-Name fuers Dialog-Wording; fehlt er, greift ein generischer Text. */
  entityName?: string
  /** Fuehrt den Delete + Reload aus (i. d. R. der `deleteFeedback`-Hook). */
  onConfirm: () => Promise<void>
}

/**
 * Lösch-Button mit Bestaetigungs-Dialog fuer einen einzelnen Feedback-Eintrag
 * (ADR-0038-Folge). Hard-Delete ist eine Kurations-Handlung → editor+. Die
 * Kurations-Sichten (Posteingang/Panel) rendern ihn — wie die Inline-Triage —
 * ohnehin nur fuer editor+; das Backend erzwingt die Rolle zusaetzlich (403).
 */
export function DeleteFeedbackButton({ entityName, onConfirm }: DeleteFeedbackButtonProps) {
  const { t } = useTranslation('feedback')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const onDelete = async () => {
    setBusy(true)
    try {
      await onConfirm()
      notify.success(t('delete.success'))
      setOpen(false)
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('delete.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={t('delete.ariaLabel')}
          className="h-8 text-xs text-destructive hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
          {t('delete.label')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('delete.dialogTitle')}</DialogTitle>
          <DialogDescription>
            {entityName !== undefined && entityName !== ''
              ? t('delete.dialogDescription', { name: entityName })
              : t('delete.dialogDescriptionGeneric')}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={busy}
            onClick={() => void onDelete()}
          >
            {t('delete.confirmLabel')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
