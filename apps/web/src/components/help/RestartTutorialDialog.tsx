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
} from '@/components/ui/dialog'

export interface RestartTutorialDialogProps {
  open: boolean
  /** Titel des Tutorials (aus dem Markdown bzw. dem Menue-Text). */
  title: string
  busy: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}

/**
 * Rueckfrage vor dem Neustart eines Tutorials (ADR-0060 §2.4). Eine
 * Darstellung fuer Tutorial-Seite, Hilfe-Startseite und das „?“-Menue in der
 * Kopfzeile. `busy` sperrt die Bestaetigung, solange der Neustart laeuft (kein
 * Doppel-Submit).
 */
export function RestartTutorialDialog({
  open,
  title,
  busy,
  onOpenChange,
  onConfirm,
}: RestartTutorialDialogProps) {
  const { t } = useTranslation('help')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('tutorial.restart.title', { title })}</DialogTitle>
          <DialogDescription>{t('tutorial.restart.body')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">{t('tutorial.restart.cancel')}</Button>
          </DialogClose>
          <Button onClick={onConfirm} disabled={busy}>
            {t('tutorial.restart.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
