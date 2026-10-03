import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/utils'

// Lernschleife C6, Spec S4a, ADR-0053 4.3: die acht Grenzen automatischer
// Freigabe. Die Liste MUSS vor der Bestaetigung sichtbar sein, nicht hinter
// einem Link, und steht nur in den Locale-Dateien (`learning.autoPolicy.limits`).
// Dieselbe Liste steht dauerhaft im Abschnitt (S4) — es darf keine Information
// geben, die nur ein einziges Mal sichtbar war.

// Reihenfolge = ADR 4.3, Punkt 1 bis 8.
export const AUTO_APPROVAL_LIMIT_KEYS = [
  'instructionData',
  'adaptiveAttacks',
  'contextual',
  'plausible',
  'userSource',
  'selfReinforcing',
  'drift',
  'rollbackLate',
] as const

// ADR-0053 3.1.3 / Anhang B: Unbestaetigtes verfaellt nach 30 Tagen, fest
// gesetzt (kein Select, Delta S4). Die API liefert den Wert nicht mit.
export const MEMORY_AUTO_EXPIRY_DAYS = 30

export function AutoApprovalLimitsList({ className }: { className?: string }) {
  const { t } = useTranslation('learning')
  return (
    <ol className={cn('flex list-decimal flex-col gap-2 pl-5 text-sm', className)}>
      {AUTO_APPROVAL_LIMIT_KEYS.map((key) => (
        <li key={key} className="break-words">
          <span className="font-medium">{t(`autoPolicy.limits.${key}.title`)}</span>{' '}
          <span className="text-muted-foreground">{t(`autoPolicy.limits.${key}.body`)}</span>
        </li>
      ))}
    </ol>
  )
}

interface AutoApprovalLimitsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  busy?: boolean
}

export function AutoApprovalLimitsDialog({
  open,
  onOpenChange,
  onConfirm,
  busy = false,
}: AutoApprovalLimitsDialogProps) {
  const { t } = useTranslation('learning')
  const isMobile = useIsMobile()
  const checkboxId = useId()
  const hintId = useId()
  const [acknowledged, setAcknowledged] = useState(false)

  // Jedes Oeffnen verlangt eine neue Bestaetigung (Delta S4: S4a bei jedem
  // Einschalten).
  useEffect(() => {
    if (open) setAcknowledged(false)
  }, [open])

  const confirmDisabled = !acknowledged || busy

  const body = (
    // Nur dieser Teil scrollt; Kopf und Buttonzeile bleiben sichtbar.
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain">
      <AutoApprovalLimitsList />
      <p className="text-sm text-muted-foreground">
        {t('autoPolicy.limits.stillHappens', { days: MEMORY_AUTO_EXPIRY_DAYS })}
      </p>
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkboxId}
          className="mt-0.5"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        <Label htmlFor={checkboxId} className="font-normal">
          {t('autoPolicy.limits.checkbox')}
        </Label>
      </div>
    </div>
  )

  const buttons = (
    <>
      <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
        {t('common:actions.cancel')}
      </Button>
      {/* `default` statt `brand`: die Oberflaeche zeichnet diese Wahl nicht
          als empfohlenen Weg aus (Spec S4a). */}
      <Button
        type="button"
        variant="default"
        disabled={confirmDisabled}
        aria-describedby={acknowledged ? undefined : hintId}
        aria-busy={busy || undefined}
        onClick={onConfirm}
      >
        {t('autoPolicy.limits.confirm')}
      </Button>
      {!acknowledged ? (
        <span id={hintId} className="sr-only">
          {t('autoPolicy.limits.confirmHint')}
        </span>
      ) : null}
    </>
  )

  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="bottom" className="h-svh rounded-t-none" data-testid="auto-approval-limits">
          <SheetHeader className="pr-8 text-left">
            <SheetTitle>{t('autoPolicy.limits.title')}</SheetTitle>
            <SheetDescription>{t('autoPolicy.limits.intro')}</SheetDescription>
          </SheetHeader>
          {body}
          <SheetFooter>{buttons}</SheetFooter>
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex flex-col overflow-hidden" data-testid="auto-approval-limits">
        <DialogHeader className="pr-8">
          <DialogTitle>{t('autoPolicy.limits.title')}</DialogTitle>
          <DialogDescription>{t('autoPolicy.limits.intro')}</DialogDescription>
        </DialogHeader>
        {body}
        <DialogFooter>{buttons}</DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
