import { cn } from '@/lib/utils'

// Zaehler-Pill neben dem H1 einer Listen-Seite (Agents, Playbooks,
// System-Prompts, Tools). Eine Quelle fuer die vier Fundstellen.
//
// Audit A12: `text-muted-foreground` auf `bg-muted` misst hell nur 4,35:1
// (#737373 auf #f5f5f5) und faellt unter WCAG AA (4,5:1). `text-foreground/70`
// misst im Browser hell 7,40:1 (#505050) und dunkel 7,80:1 (#bababa auf
// #262626). Waechter fuer alle Theme-Bloecke: `styles/brand-contrast.test.ts`.
export const COUNT_PILL_TEXT = 'text-foreground/70'

interface CountPillProps {
  count: number
  /** Zugaenglicher Name, z. B. „12 Agents\"; ohne Angabe liest der Screenreader die Zahl. */
  label?: string
  className?: string
}

export function CountPill({ count, label, className }: CountPillProps) {
  return (
    <span
      className={cn(
        'rounded-full bg-muted px-2 py-0.5 text-sm font-medium tabular-nums',
        COUNT_PILL_TEXT,
        className,
      )}
      aria-label={label}
      data-testid="count-pill"
    >
      {count}
    </span>
  )
}
