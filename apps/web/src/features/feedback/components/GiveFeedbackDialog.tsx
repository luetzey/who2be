import { MessageSquarePlus } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { FeedbackSignal, FeedbackTarget } from '@/api/types'
import { useApi } from '@/api/useApi'
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
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { notify } from '@/lib/feedback'

const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']

interface GiveFeedbackDialogProps {
  entityType: FeedbackTarget
  entityId: string
  /** Nur fuer die Dialog-Beschreibung — welches Element bewertet wird. */
  entityName: string
  /** Bezugsversion des Feedbacks (i. d. R. `current_version`). */
  version?: number
  /** Optionaler Ausloeser; ohne faellt der Dialog auf einen Outline-Button. */
  trigger?: ReactNode
}

/**
 * Dialog, mit dem ein Mensch (Editor+) gerichtetes Feedback zu einer Persona,
 * einem Playbook oder einer Resource abgibt (ADR-0038): ein Qualitaets-Signal
 * plus optionale Notiz. Landet als `entity_type`-Eintrag im Kurations-
 * Posteingang. Gegenstueck zum agentenseitigen `submit_feedback`-MCP-Tool.
 */
export function GiveFeedbackDialog({
  entityType,
  entityId,
  entityName,
  version,
  trigger,
}: GiveFeedbackDialogProps) {
  const { t } = useTranslation('feedback')
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [signal, setSignal] = useState<FeedbackSignal>('helpful')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setSignal('helpful')
    setNote('')
  }

  const onSubmit = async () => {
    setBusy(true)
    try {
      await api.submitFeedback({
        entity_type: entityType,
        entity_id: entityId,
        version,
        signal,
        note: note.trim() === '' ? undefined : note.trim(),
      })
      notify.success(t('give.success'))
      setOpen(false)
      reset()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('give.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button type="button" variant="outline">
            <MessageSquarePlus className="h-4 w-4" />
            {t('give.trigger')}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('give.title')}</DialogTitle>
          <DialogDescription>
            {t('give.description', { name: entityName })}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('give.signalLabel')}</span>
            <Select
              value={signal}
              onChange={(e) => setSignal(e.target.value as FeedbackSignal)}
              className="w-full"
            >
              {SIGNALS.map((s) => (
                <option key={s} value={s}>
                  {t(`signal.${s}`)}
                </option>
              ))}
            </Select>
          </Label>
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('give.noteLabel')}</span>
            <Textarea
              rows={4}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('give.notePlaceholder')}
              className="w-full"
            />
          </Label>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="brand"
            disabled={busy}
            onClick={() => void onSubmit()}
          >
            {t('give.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
