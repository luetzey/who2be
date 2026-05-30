import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PlaceholderRow {
  token: string
  description: string
}

const PLACEHOLDERS: readonly PlaceholderRow[] = [
  { token: '{{ persona.name }}', description: 'Name der verknüpften Persona.' },
  {
    token: '{{ persona.description }}',
    description: 'Kurzbeschreibung der Persona.',
  },
  {
    token: '{{ persona.profile }}',
    description: 'Profil-Blocks der Persona als Klartext.',
  },
  {
    token: '{{ persona.tags }}',
    description: 'Komma-getrennte Persona-Tags.',
  },
  {
    token: '{{ playbooks }}',
    description: 'Alle verlinkten Playbooks („### Name\\nBody"-Block).',
  },
  {
    token: '{{ triggers }}',
    description: 'Komma-getrennte Trigger-Keywords aller Playbooks (dedup).',
  },
  {
    token: '{{ resources }}',
    description:
      'Deduplizierte Resource-Section-Snippets aus den Playbook-Block-Refs.',
  },
]

interface PlaceholderHelpProps {
  /** Wenn `true`, wird die Card kompakter dargestellt (im Editor-Sidebar). */
  compact?: boolean
}

/**
 * Zeigt die sieben verfügbaren Liquid-Style-Placeholders an, die der
 * Render-Endpoint kennt. Wird im Template-Editor + Component-Catalog
 * eingebunden — Quelle der Wahrheit lebt im Backend
 * (`agent_render_service.py`).
 */
export function PlaceholderHelp({ compact = false }: PlaceholderHelpProps) {
  return (
    <Card data-testid="placeholder-help">
      <CardHeader>
        <CardTitle className={compact ? 'text-sm' : undefined}>
          Verfügbare Placeholders
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-2 text-sm">
          {PLACEHOLDERS.map((row) => (
            <div key={row.token} className="grid grid-cols-1 gap-1 sm:grid-cols-[12rem_1fr]">
              <dt className="font-mono text-xs text-muted-foreground">{row.token}</dt>
              <dd className="text-sm text-foreground">{row.description}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          Unbekannte Placeholders bleiben im Output stehen und werden mit{' '}
          <code>⚠ {'{{ key }}'}</code> markiert.
        </p>
      </CardContent>
    </Card>
  )
}
