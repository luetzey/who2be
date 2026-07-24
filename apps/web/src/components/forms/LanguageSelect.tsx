import { useTranslation } from 'react-i18next'

import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'

import { CONTENT_LOCALES } from './content-languages'

export interface LanguageSelectProps {
  /** Aktuell gewaehltes Sprach-Kuerzel (z. B. `'de'`). */
  value: string
  /** Liefert die neue Auswahl. */
  onChange: (next: string) => void
  /** Optionale ID-Basis fuer A11y-Verknuepfung von Label und Select. */
  idBase?: string
}

/**
 * Einzel-Auswahl der Inhalts-Sprache eines Elements (Persona / Playbook /
 * Resource / externes Tool / System-Prompt) — „Ein Element, eine Sprache"
 * (ADR-0045). Ersetzt die frühere Multi-Checkbox-Auswahl (ADR-0027): es gibt
 * keine parallelen Sprach-Tracks mehr, ein Element ist deutsch ODER
 * englisch. Der aufrufende Create-Flow liefert den Default aus der
 * Workspace-Content-Sprache (`useContentLocaleField`).
 */
export function LanguageSelect({ value, onChange, idBase = 'lang' }: LanguageSelectProps) {
  const { t } = useTranslation('common')
  const id = `${idBase}-select`

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{t('contentLocale.label')}</Label>
      <Select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="max-w-xs"
      >
        {CONTENT_LOCALES.map((lang) => (
          <option key={lang.value} value={lang.value}>
            {lang.label}
          </option>
        ))}
      </Select>
      <p className="text-sm text-muted-foreground">{t('contentLocale.helpText')}</p>
    </div>
  )
}
