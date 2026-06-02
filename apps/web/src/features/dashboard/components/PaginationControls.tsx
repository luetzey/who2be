import { ChevronLeft, ChevronRight } from 'lucide-react'

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
  if (totalPages <= 1) return null

  return (
    <nav className="flex items-center justify-between gap-3" aria-label="Aktivitaeten-Seiten">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(page - 1)}
        disabled={busy || page <= 1}
      >
        <ChevronLeft />
        Zurück
      </Button>
      <span className="text-xs text-muted-foreground" aria-live="polite">
        Seite {page} von {totalPages}
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(page + 1)}
        disabled={busy || page >= totalPages}
      >
        Weiter
        <ChevronRight />
      </Button>
    </nav>
  )
}
