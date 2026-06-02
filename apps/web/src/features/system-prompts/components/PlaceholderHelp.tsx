import { BookText, Calendar, FileText, Info, Table, User, UserCog, Wrench } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

interface SlashRow {
  command: string
  icon: typeof BookText
  description: string
}

// Quelle der Wahrheit fuer die Slash-Placeholders (Track B: Nur-BlockNote — die
// frueheren Liquid-Tokens entfallen, alles laeuft ueber Pills im Slash-Menue).
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

/**
 * Referenz-Inhalt der verfügbaren Placeholder (ohne Container). Wird sowohl im
 * Info-Popover (`PlaceholderHelp`) als auch auf der vollen Hilfe-Seite
 * (`HelpPlaceholdersPage`) verwendet — eine Quelle, zwei Darstellungen.
 */
export function PlaceholderHelpContent() {
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-muted bg-muted/40 p-3 text-sm">
        <p className="font-medium text-foreground">Was ist ein Placeholder?</p>
        <p className="mt-1 text-muted-foreground">
          Placeholders sind Platzhalter im Template, die der Server beim MCP-Read durch
          echten Inhalt ersetzt — z.&nbsp;B. den Namen der Persona oder den Body eines
          verknüpften Playbooks. So bleibt der Prompt klein und aktuell.
        </p>
        <p className="mt-2 text-muted-foreground">
          Öffne im Editor das Slash-Menü mit{' '}
          <kbd className="rounded border bg-background px-1 font-mono text-xs">/</kbd> und
          wähle einen Placeholder als Pill aus.
        </p>
      </div>

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
    </div>
  )
}

/**
 * Kompakter Info-Button mit Popover (Track B §3.2 / Punkt 12): ersetzt den
 * frueheren Dauer-Hinweis-Sidebar. Öffnet die Placeholder-Referenz on demand
 * und verlinkt auf die ausführliche Hilfe-Seite.
 */
export function PlaceholderHelp() {
  const wsPath = useWorkspacePath()
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="sm" data-testid="placeholder-help-trigger">
          <Info className="h-4 w-4" />
          Verfügbare Placeholder
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="max-h-[70vh] w-96 overflow-auto"
        data-testid="placeholder-help"
      >
        <PlaceholderHelpContent />
        <div className="mt-3 border-t border-border pt-3">
          <Link
            to={wsPath('/help/placeholders')}
            className="text-sm font-medium text-brand hover:underline"
          >
            Mehr in der Doku →
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  )
}
