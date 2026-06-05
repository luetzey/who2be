import { BookText, Calendar, FileText, Info, Table, User, UserCog, Wrench } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

interface SlashRow {
  command: string
  icon: typeof BookText
  descriptionKey: string
}

// Quelle der Wahrheit fuer die Slash-Placeholders (Track B: Nur-BlockNote — die
// frueheren Liquid-Tokens entfallen, alles laeuft ueber Pills im Slash-Menue).
const SLASH_PLACEHOLDERS: readonly SlashRow[] = [
  {
    command: '/Playbook',
    icon: BookText,
    descriptionKey: 'placeholderHelp.slash.playbook.description',
  },
  {
    command: '/Resource',
    icon: FileText,
    descriptionKey: 'placeholderHelp.slash.resource.description',
  },
  {
    command: '/Persona-Feld',
    icon: User,
    descriptionKey: 'placeholderHelp.slash.personaField.description',
  },
  {
    command: '/Persona laden (MCP)',
    icon: UserCog,
    descriptionKey: 'placeholderHelp.slash.personaLoad.description',
  },
  {
    command: '/Playbook-Katalog',
    icon: Table,
    descriptionKey: 'placeholderHelp.slash.playbookCatalog.description',
  },
  {
    command: '/Datum',
    icon: Calendar,
    descriptionKey: 'placeholderHelp.slash.date.description',
  },
  {
    command: '/MCP-Tools',
    icon: Wrench,
    descriptionKey: 'placeholderHelp.slash.mcpTools.description',
  },
]

/**
 * Referenz-Inhalt der verfügbaren Placeholder (ohne Container). Wird sowohl im
 * Info-Popover (`PlaceholderHelp`) als auch auf der vollen Hilfe-Seite
 * (`HelpPlaceholdersPage`) verwendet — eine Quelle, zwei Darstellungen.
 */
export function PlaceholderHelpContent() {
  const { t } = useTranslation('systemPrompts')
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-muted bg-muted/40 p-3 text-sm">
        <p className="font-medium text-foreground">{t('placeholderHelp.intro.heading')}</p>
        <p className="mt-1 text-muted-foreground">
          {t('placeholderHelp.intro.body')}
        </p>
        <p className="mt-2 text-muted-foreground">
          {t('placeholderHelp.intro.usage')}
        </p>
      </div>

      <section aria-labelledby="placeholder-slash-heading">
        <h3
          id="placeholder-slash-heading"
          className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
        >
          {t('placeholderHelp.slashSection.heading')}
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
                <dd className="text-sm text-foreground">{t(row.descriptionKey)}</dd>
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
  const { t } = useTranslation('systemPrompts')
  const wsPath = useWorkspacePath()
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="sm" data-testid="placeholder-help-trigger">
          <Info className="h-4 w-4" />
          {t('placeholderHelp.triggerLabel')}
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
            {t('placeholderHelp.docsLink')}
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  )
}
