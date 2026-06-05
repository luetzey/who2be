import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'

interface PaginationControlsProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  /** True, solange die naechste Seite laedt — sperrt beide Buttons. */
  busy?: boolean
}

// Seitenbasierte Vor-/Zurueck-Steuerung fuer den Activity-Feed (Track G).
// Rendert nichts, solange es nur eine Seite gibt.
export function PaginationControls({
  page,
  totalPages,
  onPageChange,
  busy = false,
}: PaginationControlsProps) {
  const { t } = useTranslation('dashboard')
  if (totalPages <= 1) return null

  return (
    <nav className="flex items-center justify-between gap-3" aria-label={t('pagination.ariaLabel')}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(page - 1)}
        disabled={busy || page <= 1}
      >
        <ChevronLeft />
        {t('common:actions.back')}
      </Button>
      <span className="text-xs text-muted-foreground" aria-live="polite">
        {t('pagination.pageOf', { page, totalPages })}
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(page + 1)}
        disabled={busy || page >= totalPages}
      >
        {t('pagination.next')}
        <ChevronRight />
      </Button>
    </nav>
  )
}
