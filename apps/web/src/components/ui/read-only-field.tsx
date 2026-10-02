import { useId } from 'react'

import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

// Audit A7 / design-language §10.2 „Werte anzeigen statt Feld faelschen":
// Ein nicht editierbarer Wert (vom System verwaltet, Viewer) steht als Lesetext
// in Feld-Optik da, nicht als gesperrtes Eingabefeld. `disabled` setzte
// `opacity-50` und drueckte Lesetext hell auf 3,71:1 — WCAG nimmt nur
// inaktive *Bedienelemente* vom Kontrastgebot aus, nicht Inhalt.
//
// `<output>` ist ein labelbares Element: `<label for>` bleibt dem Wert
// zugeordnet (Screenreader liest „Name, Agent-Builder"). `aria-live="off"`
// nimmt der impliziten Rolle `status` die Live-Ansage — der Wert ist
// statisch, kein Statusbericht.
//
// Leere Werte rendern nichts (Audit A7): ein leeres Feld mit Platzhalter
// („e.g. Default template …") sah bei verwalteten Eintraegen wie Inhalt aus.

interface ReadOnlyFieldProps {
  label: string
  /** Text oder Liste (Tags/Trigger → Kapseln). Leer → nichts rendern. */
  value: string | readonly string[] | null | undefined
  /** Monospace fuer technische Bezeichner (Slug/Alias). */
  mono?: boolean
  className?: string
  'data-testid'?: string
}

export function ReadOnlyField({
  label,
  value,
  mono = false,
  className,
  'data-testid': testId,
}: ReadOnlyFieldProps) {
  const id = useId()
  const items = Array.isArray(value) ? value.filter((item) => item.trim() !== '') : null
  const text = typeof value === 'string' ? value.trim() : ''
  if (items !== null ? items.length === 0 : text === '') return null

  return (
    <div className={cn('space-y-2', className)}>
      <Label htmlFor={id}>{label}</Label>
      <output
        id={id}
        aria-live="off"
        data-testid={testId}
        className={cn(
          // §10.2-Optik, aber in voller Vordergrundfarbe: es ist Lesetext.
          'flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-md border border-input bg-muted/50 px-3 py-2 text-sm break-words whitespace-pre-wrap text-foreground',
          mono && 'font-mono',
        )}
      >
        {items !== null
          ? items.map((item) => (
              <Badge key={item} variant="secondary" className="max-w-full break-words">
                {item}
              </Badge>
            ))
          : text}
      </output>
    </div>
  )
}
