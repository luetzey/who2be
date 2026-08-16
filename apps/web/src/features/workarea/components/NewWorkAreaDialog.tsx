import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { notify } from '@/lib/feedback'

interface NewWorkAreaDialogProps {
  /** Wird nach erfolgreicher Anlage aufgerufen (Liste neu laden). */
  onCreated: () => void
}

/**
 * Anlage eines GETEILTEN Arbeitsbereichs (editor+).
 *
 * Nur shared Areas entstehen explizit — die private Area eines Agenten legt der
 * Server beim ersten Zugriff selbst an. Ohne diesen Dialog gaebe es fuer einen
 * Betreiber gar keinen Weg, einen Team-Bereich anzulegen: die Grant-Vergabe
 * setzt einen geteilten Bereich voraus.
 */
export function NewWorkAreaDialog({ onCreated }: NewWorkAreaDialogProps) {
  const { t } = useTranslation('workarea')
  const api = useApi()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [retention, setRetention] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    const trimmed = name.trim()
    if (trimmed === '') {
      setError(t('new.nameRequired'))
      return
    }
    let retentionDays: number | null = null
    if (retention.trim() !== '') {
      const parsed = Number(retention.trim())
      if (!Number.isInteger(parsed) || parsed <= 0) {
        setError(t('new.retentionInvalid'))
        return
      }
      retentionDays = parsed
    }
    setBusy(true)
    setError(null)
    try {
      await api.createWorkArea({ name: trimmed, retention_days: retentionDays })
      notify.success(t('new.createdToast', { name: trimmed }))
      setOpen(false)
      setName('')
      setRetention('')
      onCreated()
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : t('new.actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="brand"
          disabled={isViewer}
          title={isViewer ? t('new.viewerReadOnly') : undefined}
        >
          <Plus className="h-4 w-4" />
          {t('list.newArea')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('new.title')}</DialogTitle>
          <DialogDescription>{t('new.description')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('new.nameLabel')}</span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('new.namePlaceholder')}
              className="w-full"
            />
          </Label>
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('new.retentionLabel')}</span>
            <Input
              value={retention}
              onChange={(e) => setRetention(e.target.value)}
              placeholder={t('new.retentionPlaceholder')}
              inputMode="numeric"
              className="w-full"
            />
            <span className="text-xs text-muted-foreground">{t('new.retentionHelp')}</span>
          </Label>
          {error !== null ? <ErrorAlert message={error} /> : null}
        </div>
        <DialogFooter>
          <Button type="button" onClick={() => void submit()} disabled={busy}>
            {t('new.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
