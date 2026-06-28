import { TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { SystemFeedbackCategory } from '@/api/types'
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

const CATEGORIES: readonly SystemFeedbackCategory[] = ['technical', 'mcp', 'performance', 'other']

interface ReportProblemDialogProps {
  /** Wird nach erfolgreichem Melden aufgerufen (z. B. Posteingang neu laden). */
  onReported?: () => void
}

/**
 * Dialog zum Melden eines zielloses System-/MCP-Problems (ADR-0038-Folge):
 * Kategorie + Beschreibung. Landet als `entity_type='system'`-Eintrag im
 * Kurations-Posteingang. Fuer jede Rolle offen (feedback_write ist fuer
 * Mensch-Tokens ein No-Op); das Backend nimmt es entgegen.
 */
export function ReportProblemDialog({ onReported }: ReportProblemDialogProps) {
  const { t } = useTranslation('feedback')
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState<SystemFeedbackCategory>('technical')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const reset = () => {
    setCategory('technical')
    setNote('')
  }

  const onSubmit = async () => {
    if (note.trim() === '') return
    setBusy(true)
    try {
      await api.submitSystemFeedback({ category, note: note.trim() })
      notify.success(t('report.success'))
      setOpen(false)
      reset()
      onReported?.()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('report.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          <TriangleAlert className="h-4 w-4" />
          {t('report.label')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('report.dialogTitle')}</DialogTitle>
          <DialogDescription>{t('report.dialogDescription')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('report.categoryLabel')}</span>
            <Select
              value={category}
              onChange={(e) => setCategory(e.target.value as SystemFeedbackCategory)}
              className="w-full"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(`systemCategory.${c}`)}
                </option>
              ))}
            </Select>
          </Label>
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('report.noteLabel')}</span>
            <Textarea
              rows={4}
              required
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('report.notePlaceholder')}
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
            disabled={busy || note.trim() === ''}
            onClick={() => void onSubmit()}
          >
            {t('report.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
