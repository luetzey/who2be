import type { ReactNode } from 'react'

/**
 * Markiert eine noch zu befuellende Stelle im Rechtstext deutlich sichtbar als
 * `<PLATZHALTER: …>`. Bewusst auffaellig (Brand-Token, gestrichelter Rahmen,
 * Monospace), damit kein Platzhalter versehentlich live geht. Der finale Text
 * (Firmendaten/Anwaltstext, CL4) ersetzt diese Komponente 1:1 durch Fliesstext.
 */
export function Placeholder({ children }: { children: ReactNode }) {
  return (
    <mark
      data-placeholder
      className="mx-0.5 rounded-sm border border-dashed border-brand bg-brand/10 px-1 py-0.5 font-mono text-xs font-medium text-brand"
    >
      {'<PLATZHALTER: '}
      {children}
      {'>'}
    </mark>
  )
}
