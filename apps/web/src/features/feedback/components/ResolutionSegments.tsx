import { useTranslation } from 'react-i18next'

import type { FeedbackResolution } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// Segmentierte Status-Steuerung fuer einen Feedback-Eintrag (Design-Handoff
// „Feedback"): Offen / In Arbeit / Erledigt / Verworfen. Ersetzt das fruehere
// Resolution-Select im Posteingang und in der Detail-Ereignisliste — gleiche
// Business-Logik (setFeedbackResolution), nur andere Darstellung.
//
// „Offen" (resolution === null) ist der Ausgangszustand und laesst sich nicht
// aktiv setzen (kein Reopen-Endpunkt) — der Button markiert den Zustand, ist
// aber deaktiviert. Lebt im Feature (kein geteiltes UI-Primitive).

// Reihenfolge fest; 'open' fuehrt, dann die drei echten Resolutions.
const SEGMENTS: readonly (FeedbackResolution | 'open')[] = [
  'open',
  'in_progress',
  'addressed',
  'dismissed',
]

interface ResolutionSegmentsProps {
  value: FeedbackResolution | null
  onChange: (resolution: FeedbackResolution) => void
  /** Fuer eindeutige aria-Labels je Zeile (z. B. Element-/Ereignis-Name). */
  name: string
  disabled?: boolean
}

export function ResolutionSegments({ value, onChange, name, disabled }: ResolutionSegmentsProps) {
  const { t } = useTranslation('feedback')
  const current = value ?? 'open'

  return (
    <span
      role="group"
      aria-label={`${t('resolution.label')} — ${name}`}
      className="inline-flex gap-0.5 rounded-lg bg-muted p-0.5"
    >
      {SEGMENTS.map((segment) => {
        const active = segment === current
        // „Offen" hat keinen Reopen-Endpunkt → reine Zustandsanzeige.
        const isOpen = segment === 'open'
        return (
          <Button
            key={segment}
            type="button"
            variant="ghost"
            size="sm"
            aria-pressed={active}
            aria-label={`${t(`inbox.status.${segment}`)} — ${name}`}
            disabled={disabled || isOpen}
            onClick={isOpen ? undefined : () => onChange(segment)}
            className={cn(
              'h-7 rounded-md px-2.5 text-xs font-medium',
              // Aktives Segment hebt sich neutral (Surface + Shadow), nicht per
              // Brand-Fill — Brand-Tinte bleibt CTAs vorbehalten (§2.2/§9.1).
              active
                ? 'bg-card text-foreground shadow-card disabled:opacity-100'
                : 'text-muted-foreground hover:bg-transparent hover:text-foreground',
            )}
          >
            {t(`inbox.status.${segment}`)}
          </Button>
        )
      })}
    </span>
  )
}
