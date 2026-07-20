import { X } from 'lucide-react'
import {
  forwardRef,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react'

import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export interface TagInputProps {
  value: string[]
  onChange: (next: string[]) => void
  /**
   * Loader fuer Vorschlagsliste (z. B. `api.listPlaybookTags`). Wird einmal
   * beim Mount aufgerufen. Faengt Fehler ab und liefert leere Liste — der
   * TagInput bleibt manuell befuellbar, wenn der Endpoint (noch) 404
   * antwortet.
   */
  loadSuggestions?: () => Promise<string[]>
  placeholder?: string
  id?: string
  /** Sichtbares Label-`id`, wird auf das Eingabefeld referenziert. */
  ariaLabelledby?: string
  className?: string
  disabled?: boolean
}

function normalize(raw: string): string {
  return raw.trim()
}

/**
 * Multi-Select-Tag-Picker im shadcn-Stil. Pills + freie Texteingabe;
 * Vorschlaege aus einem optionalen Loader. Enter / Komma uebernehmen den
 * aktuellen Wert, Backspace im leeren Feld entfernt den letzten Tag.
 *
 * A11y-Vertrag (siehe design-language.md §11): Input traegt
 * `role="combobox"` + `aria-expanded`, das Vorschlag-Popover ist eine
 * `role="listbox"` mit `role="option"`-Treffern. Jede Pill hat einen
 * Entfernen-Button mit `aria-label="Tag X entfernen"`.
 */
export const TagInput = forwardRef<HTMLInputElement, TagInputProps>(function TagInput(
  {
    value,
    onChange,
    loadSuggestions,
    placeholder,
    id,
    ariaLabelledby,
    className,
    disabled = false,
  },
  ref,
) {
  const reactId = useId()
  const inputId = id ?? `tag-input-${reactId}`
  const listboxId = `${inputId}-listbox`
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (loadSuggestions === undefined) {
      return
    }
    let cancelled = false
    loadSuggestions()
      .then((items) => {
        if (!cancelled) {
          setSuggestions(items)
        }
      })
      .catch(() => {
        // Fallback: bleibt leer, User kann manuell Tags eintippen.
        if (!cancelled) {
          setSuggestions([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [loadSuggestions])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const selected = new Set(value.map((tag) => tag.toLowerCase()))
    return suggestions
      .filter((tag) => !selected.has(tag.toLowerCase()))
      .filter((tag) => q.length === 0 || tag.toLowerCase().includes(q))
      .slice(0, 10)
  }, [suggestions, query, value])

  const canCreate = useMemo(() => {
    const candidate = normalize(query)
    if (candidate.length === 0) {
      return false
    }
    const lower = candidate.toLowerCase()
    return (
      !value.some((tag) => tag.toLowerCase() === lower) &&
      !suggestions.some((tag) => tag.toLowerCase() === lower)
    )
  }, [query, value, suggestions])

  const addTag = useCallback(
    (raw: string) => {
      const next = normalize(raw)
      if (next.length === 0) {
        return
      }
      const lower = next.toLowerCase()
      if (value.some((tag) => tag.toLowerCase() === lower)) {
        setQuery('')
        return
      }
      onChange([...value, next])
      setQuery('')
    },
    [value, onChange],
  )

  const removeTag = useCallback(
    (tag: string) => {
      onChange(value.filter((entry) => entry !== tag))
    },
    [value, onChange],
  )

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      if (query.trim().length > 0) {
        addTag(query)
      }
      return
    }
    if (event.key === 'Backspace' && query.length === 0 && value.length > 0) {
      event.preventDefault()
      removeTag(value[value.length - 1])
    }
  }

  // Klick ausserhalb schliesst das Popover.
  useEffect(() => {
    if (!open) {
      return
    }
    const onDocClick = (event: MouseEvent) => {
      if (
        containerRef.current !== null &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  return (
    <div ref={containerRef} className={cn('relative flex flex-col gap-2', className)}>
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-input bg-background px-2 py-2">
        {value.map((tag) => (
          <Badge key={tag} variant="secondary" className="flex items-center gap-1">
            <span>{tag}</span>
            <button
              type="button"
              aria-label={`Tag ${tag} entfernen`}
              className="rounded-full p-0.5 hover:bg-muted disabled:cursor-not-allowed"
              onClick={() => removeTag(tag)}
              disabled={disabled}
            >
              {/* size-3 bewusst (funktionaler Sonderfall §8): Remove-X im
                  kompakten Badge — size-4 wuerde die Tag-Pille aufblaehen. */}
              <X className="size-3" />
            </button>
          </Badge>
        ))}
        <Input
          ref={ref}
          id={inputId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-labelledby={ariaLabelledby}
          className="h-8 min-w-32 flex-1 border-0 p-1 shadow-none focus-visible:ring-0"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? placeholder : undefined}
          disabled={disabled}
        />
      </div>
      {open && (filtered.length > 0 || canCreate) ? (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Tag-Vorschlaege"
          className="absolute top-full z-10 mt-1 w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-popover"
        >
          {filtered.map((tag) => (
            <li
              key={tag}
              role="option"
              aria-selected={false}
              className="cursor-pointer px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
              onMouseDown={(event) => {
                event.preventDefault()
                addTag(tag)
              }}
            >
              {tag}
            </li>
          ))}
          {canCreate ? (
            <li
              role="option"
              aria-selected={false}
              className="cursor-pointer border-t px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              onMouseDown={(event) => {
                event.preventDefault()
                addTag(query)
              }}
            >
              Neu erstellen: „{normalize(query)}"
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  )
})
