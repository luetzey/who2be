import { MessageSquarePlus } from 'lucide-react'
import { useState, type ComponentType, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import type { FeedbackSignal } from '@/api/types'
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
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  useGiveFeedbackForm,
  type GiveFeedbackFormState,
  type GiveFeedbackTarget,
} from '@/hooks/useFeedbackForms'
import { useIsMobile } from '@/hooks/useMediaQuery'

const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']

/**
 * Navigations-State der Vollbildseiten „Feedback geben“/„Problem melden“
 * (Mobil-Spec W4=b): `from` ist die Ausgangsseite inkl. Query (z. B.
 * `?tab=`), `name` der Elementname fuer die Beschreibung. Beides fehlt bei
 * einem Deep-Link — dann faellt die Seite auf die Element-Detailseite zurueck.
 */
export interface FeedbackComposeState {
  from?: string
  name?: string
}

interface GiveFeedbackFormProps {
  form: GiveFeedbackFormState
  /** „Abbrechen“ der Huelle (Dialog: `DialogClose`, Seite: Zurueck). */
  cancel: ReactNode
  /** Fusszeilen-Container (Dialog: `DialogFooter`, Seite: eigene Leiste). */
  Footer: ComponentType<{ children: ReactNode }>
}

/** Felder + Fusszeile des Feedback-Formulars — geteilt von Dialog und Seite. */
export function GiveFeedbackForm({ form, cancel, Footer }: GiveFeedbackFormProps) {
  const { t } = useTranslation('feedback')
  return (
    <>
      <div className="flex flex-col gap-4">
        <Label className="flex flex-col items-start gap-1 text-sm font-normal">
          <span className="font-medium">{t('give.signalLabel')}</span>
          <Select
            value={form.signal}
            onChange={(e) => form.setSignal(e.target.value as FeedbackSignal)}
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
            value={form.note}
            onChange={(e) => form.setNote(e.target.value)}
            placeholder={t('give.notePlaceholder')}
            className="w-full"
          />
        </Label>
      </div>
      <Footer>
        {cancel}
        <Button
          type="button"
          variant="brand"
          disabled={form.busy}
          onClick={() => void form.submit()}
        >
          {t('give.submit')}
        </Button>
      </Footer>
    </>
  )
}

interface GiveFeedbackDialogProps extends GiveFeedbackTarget {
  /** Nur fuer die Dialog-Beschreibung — welches Element bewertet wird. */
  entityName: string
  /** Optionaler Ausloeser; ohne faellt der Dialog auf einen Outline-Button. */
  trigger?: ReactNode
}

/**
 * Dialog, mit dem ein Mensch (Editor+) gerichtetes Feedback zu einer Persona,
 * einem Playbook oder einer Resource abgibt (ADR-0038): ein Qualitaets-Signal
 * plus optionale Notiz. Landet als `entity_type`-Eintrag im Kurations-
 * Posteingang. Gegenstueck zum agentenseitigen `submit_feedback`-MCP-Tool.
 *
 * Mobil-Spec W4=b: unterhalb `md` oeffnet der Ausloeser statt des Dialogs die
 * Vollbildseite `/feedback/give/:entityType/:entityId` (lange Notizen auf dem
 * Telefon). Ab `md` bleibt der Dialog.
 */
export function GiveFeedbackDialog(props: GiveFeedbackDialogProps) {
  const isMobile = useIsMobile()
  return isMobile ? <GiveFeedbackPageLink {...props} /> : <GiveFeedbackModal {...props} />
}

function GiveFeedbackPageLink({ entityType, entityId, entityName, version, trigger }: GiveFeedbackDialogProps) {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const location = useLocation()
  const query = version === undefined ? '' : `?version=${version}`
  const state: FeedbackComposeState = {
    from: `${location.pathname}${location.search}`,
    name: entityName,
  }
  return (
    <Button asChild variant="outline">
      <Link to={wsPath(`/feedback/give/${entityType}/${entityId}${query}`)} state={state}>
        {trigger ?? (
          <>
            <MessageSquarePlus className="h-4 w-4" />
            {t('give.trigger')}
          </>
        )}
      </Link>
    </Button>
  )
}

function GiveFeedbackModal({ entityType, entityId, entityName, version, trigger }: GiveFeedbackDialogProps) {
  const { t } = useTranslation('feedback')
  const [open, setOpen] = useState(false)
  const form = useGiveFeedbackForm({ entityType, entityId, version }, () => setOpen(false))

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
        <GiveFeedbackForm
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
