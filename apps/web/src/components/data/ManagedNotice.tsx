import { Lock } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

interface ManagedNoticeProps {
  /**
   * Zeigt zusaetzlich den Hinweis, dass der Agent dupliziert werden kann, um
   * eine eigene, editierbare Kopie zu erhalten. Nur auf der Agent-Detail-Page
   * sinnvoll (dort gibt es den Duplizieren-Button).
   */
  showDuplicateHint?: boolean
  className?: string
}

/**
 * Hinweis-Banner fuer vom System verwaltete (gesperrte) Aggregate — z. B. den
 * geseedeten Builder. Erklaert, dass Aenderungen zentral gepflegt werden und
 * User-Mutationen gesperrt sind (das Backend erzwingt das mit 403
 * `managed_aggregate`). Die Detail-Pages rendern dann ihre Editoren read-only
 * und blenden Lösch-/Status-Aktionen aus.
 */
export function ManagedNotice({ showDuplicateHint = false, className }: ManagedNoticeProps) {
  const { t } = useTranslation('common')
  return (
    <Alert
      className={cn('border-brand/30 bg-brand/5 [&>svg]:text-muted-foreground', className)}
      data-testid="managed-notice"
    >
      <Lock className="h-4 w-4" />
      <AlertTitle>{t('managed.title')}</AlertTitle>
      <AlertDescription>
        <p>{t('managed.body')}</p>
        {showDuplicateHint ? (
          <p className="mt-1 font-medium text-foreground">{t('managed.duplicateHint')}</p>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
