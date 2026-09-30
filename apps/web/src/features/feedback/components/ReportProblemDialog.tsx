import { TriangleAlert } from 'lucide-react'
import { useState, type ComponentType, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import type { SystemFeedbackCategory } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import type { FeedbackComposeState } from '@/components/feedback/GiveFeedbackDialog'
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
import { useReportProblemForm, type ReportProblemFormState } from '@/hooks/useFeedbackForms'
import { useIsMobile } from '@/hooks/useMediaQuery'

const CATEGORIES: readonly SystemFeedbackCategory[] = ['technical', 'mcp', 'performance', 'other']

interface ReportProblemFormProps {
  form: ReportProblemFormState
  /** „Abbrechen“ der Huelle (Dialog: `DialogClose`, Seite: Zurueck). */
  cancel: ReactNode
  /** Fusszeilen-Container (Dialog: `DialogFooter`, Seite: eigene Leiste). */
  Footer: ComponentType<{ children: ReactNode }>
}

/** Felder + Fusszeile von „Problem melden“ — geteilt von Dialog und Seite. */
export function ReportProblemForm({ form, cancel, Footer }: ReportProblemFormProps) {
  const { t } = useTranslation('feedback')
  return (
    <>
      <div className="flex flex-col gap-4">
        <Label className="flex flex-col items-start gap-1 text-sm font-normal">
          <span className="font-medium">{t('report.categoryLabel')}</span>
          <Select
            value={form.category}
            onChange={(e) => form.setCategory(e.target.value as SystemFeedbackCategory)}
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
            value={form.note}
            onChange={(e) => form.setNote(e.target.value)}
            placeholder={t('report.notePlaceholder')}
            className="w-full"
          />
        </Label>
      </div>
      <Footer>
        {cancel}
        <Button
          type="button"
          variant="brand"
          disabled={form.busy || form.note.trim() === ''}
          onClick={() => void form.submit()}
        >
          {t('report.submit')}
        </Button>
      </Footer>
    </>
  )
}

interface ReportProblemDialogProps {
  /** Wird nach erfolgreichem Melden aufgerufen (z. B. Posteingang neu laden). */
  onReported?: () => void
}

/**
 * Dialog zum Melden eines zielloses System-/MCP-Problems (ADR-0038-Folge):
 * Kategorie + Beschreibung. Landet als `entity_type='system'`-Eintrag im
 * Kurations-Posteingang. Fuer jede Rolle offen (feedback_write ist fuer
 * Mensch-Tokens ein No-Op); das Backend nimmt es entgegen.
 *
 * Mobil-Spec W4=b: unterhalb `md` fuehrt der Ausloeser auf die Vollbildseite
 * `/feedback/report`; ab `md` bleibt der Dialog. Nach dem Melden auf der
 * Seite laedt die Uebersicht beim Zurueckkehren ohnehin neu — `onReported`
 * gilt deshalb nur fuer den Dialog.
 */
export function ReportProblemDialog({ onReported }: ReportProblemDialogProps) {
  const isMobile = useIsMobile()
  return isMobile ? <ReportProblemPageLink /> : <ReportProblemModal onReported={onReported} />
}

function ReportProblemPageLink() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const location = useLocation()
  const state: FeedbackComposeState = { from: `${location.pathname}${location.search}` }
  return (
    <Button asChild variant="outline">
      <Link to={wsPath('/feedback/report')} state={state}>
        <TriangleAlert className="h-4 w-4" />
        {t('report.label')}
      </Link>
    </Button>
  )
}

function ReportProblemModal({ onReported }: ReportProblemDialogProps) {
  const { t } = useTranslation('feedback')
  const [open, setOpen] = useState(false)
  const form = useReportProblemForm(() => {
    setOpen(false)
    onReported?.()
  })

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
        <ReportProblemForm
          form={form}
          Footer={DialogFooter}
          cancel={
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={form.busy}>
                {t('common:actions.cancel')}
              </Button>
            </DialogClose>
          }
        />
      </DialogContent>
    </Dialog>
  )
}
