import { BookText, Calendar, FileText, Table, User, UserCog, Wrench, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface SlashRow {
  command: string
  icon: typeof BookText
  description: string
}

const SLASH_PLACEHOLDERS: readonly SlashRow[] = [
  {
    command: '/Playbook',
    icon: BookText,
    description: 'Body eines verknüpften Playbooks einfügen.',
  },
  {
    command: '/Resource',
    icon: FileText,
    description: 'Body einer Resource einfügen.',
  },
  {
    command: '/Persona-Feld',
    icon: User,
    description:
      'Bettet Name, Beschreibung, das volle Profil, nur den Profil-Inhalt oder nur die Modi ein.',
  },
  {
    command: '/Persona laden (MCP)',
    icon: UserCog,
    description:
      'Bettet keinen Inhalt ein, sondern weist den Agenten an, seine Persona zur Laufzeit via get_persona(...) selbst zu laden und ihre Modi anzuwenden.',
  },
  {
    command: '/Playbook-Katalog',
    icon: Table,
    description:
      'Tabelle der zugeordneten Playbooks (Name, Trigger, Aufruf, Beschreibung) — briefs den Agenten, was er wann via fetch_playbook(...) laden kann. Wahlweise alle oder nur getriggerte.',
  },
  {
    command: '/Datum',
    icon: Calendar,
    description: 'Aktuelles Datum (ISO oder lesbar).',
  },
  {
    command: '/MCP-Tools',
    icon: Wrench,
    description:
      'Liste der MCP-Werkzeuge mit Signatur und Kurzbeschreibung. Schreib drumherum die Reihenfolge ("zuerst list_triggers, dann fetch_playbook"), damit der LLM die Tools richtig nutzt.',
  },
]

interface LiquidRow {
  token: string
  description: string
}

const LIQUID_PLACEHOLDERS: readonly LiquidRow[] = [
  { token: '{{ persona.name }}', description: 'Name der verknüpften Persona.' },
  { token: '{{ persona.description }}', description: 'Kurzbeschreibung der Persona.' },
  { token: '{{ persona.profile }}', description: 'Profil-Blocks der Persona als Klartext.' },
  { token: '{{ persona.tags }}', description: 'Komma-getrennte Persona-Tags.' },
  {
    token: '{{ playbooks }}',
    description:
      'Alle verlinkten Playbooks („### Name\\nBody"-Block). Für neue Templates besser MCP-Tool list_playbooks/fetch_playbook nutzen — kleinerer Prompt, frischere Daten.',
  },
  {
    token: '{{ triggers }}',
    description:
      'Komma-getrennte Trigger-Keywords aller Playbooks (dedup). Empfehlung: stattdessen MCP-Tool list_triggers nutzen — liefert Trigger→Playbook-Tabelle.',
  },
  {
    token: '{{ resources }}',
    description: 'Deduplizierte Resource-Section-Snippets aus den Playbook-Block-Refs.',
  },
]

interface PlaceholderHelpProps {
  /** Wenn `true`, wird die Card kompakter dargestellt (im Editor-Sidebar). */
  compact?: boolean
}

const HINT_STORAGE_KEY = 'who2be.placeholder-help.hint-dismissed'

function useDismissedFlag(key: string): readonly [boolean, (next: boolean) => void] {
  const [dismissed, setDismissed] = useState(false)
  // Initial-Read im Effekt — vermeidet SSR-Hydration-Mismatches und ist
  // robust gegen Storage-Disabled-Browser (`storage` throws → bleibt `false`).
  useEffect(() => {
    try {
      setDismissed(window.localStorage.getItem(key) === '1')
    } catch {
      /* localStorage nicht verfuegbar — Default false bleibt */
    }
  }, [key])
  const persist = (next: boolean): void => {
    setDismissed(next)
    try {
      if (next) {
        window.localStorage.setItem(key, '1')
      } else {
        window.localStorage.removeItem(key)
      }
    } catch {
      /* siehe oben */
    }
  }
  return [dismissed, persist]
}

/**
 * Listet die verfügbaren Placeholders in zwei Sektionen: die vier
 * BlockNote-Slash-Befehle (Welle 5) und die sieben Liquid-Style-Tokens, die
 * der Render-Endpoint im Plain-Text-Modus kennt. Quelle der Wahrheit fuer die
 * Liquid-Tokens lebt im Backend (`agent_render_service.py`); die BlockNote-
 * Placeholders sind im Welle-5-Spec festgeschrieben.
 *
 * Ein einleitender Hinweis erklaert Einsteigern, was ein Placeholder ist; er
 * laesst sich pro Browser dauerhaft ausblenden (localStorage).
 */
export function PlaceholderHelp({ compact = false }: PlaceholderHelpProps) {
  const [hintDismissed, setHintDismissed] = useDismissedFlag(HINT_STORAGE_KEY)

  return (
    <Card data-testid="placeholder-help">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
        <CardTitle className={compact ? 'text-sm' : undefined}>
          Verfügbare Placeholders
        </CardTitle>
        {hintDismissed ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-2 py-1 text-xs"
            onClick={() => setHintDismissed(false)}
          >
            Hinweis einblenden
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {!hintDismissed ? (
          <div
            className="relative rounded-md border border-muted bg-muted/40 p-3 pr-9 text-sm"
            data-testid="placeholder-help-hint"
          >
            <p className="font-medium text-foreground">Was ist ein Placeholder?</p>
            <p className="mt-1 text-muted-foreground">
              Placeholders sind Platzhalter im Template, die der Server beim MCP-Read
              durch echten Inhalt ersetzt — z.&nbsp;B. den Namen der Persona oder den
              Body eines verknüpften Playbooks. So bleibt der Prompt klein und
              aktuell, ohne dass du Inhalte manuell kopieren musst.
            </p>
            <p className="mt-2 text-muted-foreground">
              Im BlockNote-Editor öffnest du das Slash-Menü mit{' '}
              <kbd className="rounded border bg-background px-1 font-mono text-xs">
                /
              </kbd>{' '}
              und wählst einen Placeholder als Pill aus. Im Plain-Text-Modus tippst
              du die Liquid-Notation direkt — siehe Liste unten.
            </p>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1 h-7 w-7"
              onClick={() => setHintDismissed(true)}
              aria-label="Hinweis ausblenden"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : null}

        <section aria-labelledby="placeholder-slash-heading">
          <h3
            id="placeholder-slash-heading"
            className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
          >
            BlockNote-Editor (Slash-Menü)
          </h3>
          <dl className="grid gap-2 text-sm">
            {SLASH_PLACEHOLDERS.map((row) => {
              const Icon = row.icon
              return (
                <div
                  key={row.command}
                  className="grid grid-cols-1 gap-1 sm:grid-cols-[10rem_1fr]"
                >
                  <dt className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                    {row.command}
                  </dt>
                  <dd className="text-sm text-foreground">{row.description}</dd>
                </div>
              )
            })}
          </dl>
        </section>

        <section aria-labelledby="placeholder-liquid-heading">
          <h3
            id="placeholder-liquid-heading"
            className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
          >
            Plain-Text-Editor (Liquid-Tokens)
          </h3>
          <dl className="grid gap-2 text-sm">
            {LIQUID_PLACEHOLDERS.map((row) => (
              <div
                key={row.token}
                className="grid grid-cols-1 gap-1 sm:grid-cols-[12rem_1fr]"
              >
                <dt className="font-mono text-xs text-muted-foreground">{row.token}</dt>
                <dd className="text-sm text-foreground">{row.description}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            Unbekannte Placeholders bleiben im Output stehen und werden mit{' '}
            <code>⚠ {'{{ key }}'}</code> markiert.
          </p>
        </section>
      </CardContent>
    </Card>
  )
}
