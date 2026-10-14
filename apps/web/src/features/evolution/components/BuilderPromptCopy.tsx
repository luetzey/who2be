import { Copy } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'

interface BuilderPromptCopyProps {
  /** Text zum Einfuegen im Client. Er enthaelt nur IDs und Namen, nie Inhalte. */
  prompt: string
  /** Sichtbares Label der Textarea; ohne Angabe „Im Client einfügen:“. */
  label?: string
  testId?: string
}

/**
 * Kopierblock fuer den Builder im Client (Muster `BuilderCopy` aus D6g,
 * E5-Delta §8): eine readOnly-Textarea mit Label und ein Knopf „Kopieren“,
 * der den Erfolg per Toast (`role=status`) meldet.
 *
 * Datenschutz (D-Delta S5): Der Aufrufer baut den Text nur aus IDs und
 * Namen. Freitexte aus Reviews oder Rueckmeldungen koennen personenbezogen
 * sein und gehoeren nicht in die Zwischenablage. Wird in E5f (Review
 * vorbereiten) wiederverwendet.
 */
export function BuilderPromptCopy({ prompt, label, testId }: BuilderPromptCopyProps) {
  const { t } = useTranslation(['sessions', 'common'])
  const id = useId()

  const onCopy = () => {
    void copyToClipboard(prompt)
      .then(() => notify.success(t('sessions:copy.copied')))
      .catch((cause: unknown) => {
        notify.error(cause instanceof Error ? cause.message : t('common:error.generic'))
      })
  }

  return (
    <div className="flex min-w-0 flex-col gap-2" data-testid={testId}>
      <Label htmlFor={id}>{label ?? t('sessions:copy.label')}</Label>
      <Textarea
        id={id}
        readOnly
        autoGrow={false}
        rows={4}
        value={prompt}
        className="font-mono text-xs break-words"
        onFocus={(event) => event.currentTarget.select()}
      />
      {/* 390 px: volle Breite unter dem Text, 44 px hoch (D6g). */}
      <Button
        type="button"
        variant="outline"
        className="min-h-11 w-full sm:min-h-9 sm:w-auto sm:self-start"
        onClick={onCopy}
      >
        <Copy aria-hidden="true" />
        {t('sessions:copy.button')}
      </Button>
    </div>
  )
}
