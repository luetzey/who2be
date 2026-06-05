import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

import { CONTENT_LANGUAGES } from './content-languages'

export interface LanguageSelectProps {
  /** Aktuell gewaehlte Sprach-Kuerzel (z. B. `['de']`). */
  value: string[]
  /** Liefert die neue Auswahl; mindestens eine Sprache bleibt erzwungen. */
  onChange: (next: string[]) => void
  /** Optionale ID-Basis fuer A11y-Verknuepfung von Label und Checkbox. */
  idBase?: string
}

/**
 * Mehrfach-Auswahl der Inhalts-Sprachen fuer den Create-Flow. Genau eine
 * Sprache muss gewaehlt bleiben — das Abwaehlen der letzten Sprache ist
 * unterbunden (Backend verlangt `locales` mit min. einem Eintrag).
 */
export function LanguageSelect({ value, onChange, idBase = 'lang' }: LanguageSelectProps) {
  function toggle(code: string, checked: boolean): void {
    if (checked) {
      if (value.includes(code)) return
      // Reihenfolge stabil entlang CONTENT_LANGUAGES halten.
      onChange(CONTENT_LANGUAGES.map((l) => l.value).filter((c) => c === code || value.includes(c)))
      return
    }
    const next = value.filter((c) => c !== code)
    // Letzte Sprache nicht abwaehlbar — sonst haette das Backend kein `locales`.
    if (next.length === 0) return
    onChange(next)
  }

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium text-foreground">Sprachen</legend>
      <p className="text-sm text-muted-foreground">
        Je gewaehlter Sprache wird eine eigene Inhalts-Variante angelegt.
      </p>
      <div className="flex flex-wrap gap-4">
        {CONTENT_LANGUAGES.map((lang) => {
          const id = `${idBase}-${lang.value}`
          const checked = value.includes(lang.value)
          return (
            <Label key={lang.value} htmlFor={id} className="flex items-center gap-2 font-normal">
              <Checkbox
                id={id}
                checked={checked}
                onChange={(event) => toggle(lang.value, event.target.checked)}
              />
              {lang.label}
            </Label>
          )
        })}
      </div>
    </fieldset>
  )
}
