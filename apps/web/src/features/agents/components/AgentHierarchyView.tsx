import { ChevronRight, FileText, GitBranch, Users, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Agent, Persona, Playbook, SystemPromptTemplate, VersionStatus } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EntityIcon, type EntityTone } from '@/components/data/EntityIcon'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

interface AgentHierarchyViewProps {
  agent: Agent
  persona: Persona | null
  template: SystemPromptTemplate | null
  playbooks: Playbook[]
}

// Kleine Uppercase-Bereichsueberschrift (Design-Handoff „Detail-Redesign":
// „Zusammensetzung" / „System-Prompt" / „Persona").
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
      {children}
    </div>
  )
}

// Prominente Verweiszeile fuer System-Prompt/Persona: Icon-Kachel + Caption
// (System-Prompt/Persona) + Name-Link + Versions-Badge + optionaler Status.
// Der `<Link>` umschliesst bewusst nur den Namen — der zugaengliche Name der
// Verknuepfung bleibt exakt der Entitaetsname (Caption/Badges liegen daneben).
function PrimaryRow({
  icon,
  tone,
  caption,
  name,
  href,
  version,
  status,
  testId,
}: {
  icon: LucideIcon
  tone: EntityTone
  caption: string
  name: string
  href: string
  version?: number
  status?: VersionStatus
  testId?: string
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg px-2 py-2 transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/50"
      data-testid={testId}
    >
      <EntityIcon icon={icon} tone={tone} size="sm" />
      <div className="min-w-0 flex-1">
        <SectionLabel>{caption}</SectionLabel>
        <div className="mt-0.5 flex flex-wrap items-center gap-2">
          <Link
            to={href}
            className="min-w-0 truncate rounded-sm font-semibold text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {name}
          </Link>
          {version !== undefined ? (
            <Badge variant="outline" className="tabular-nums">
              v{version}
            </Badge>
          ) : null}
          {status !== undefined ? <StatusBadge status={status} /> : null}
        </div>
      </div>
      <ChevronRight className="size-4 flex-none text-muted-foreground/60" aria-hidden="true" />
    </div>
  )
}

// Kompakte Chip-/Link-Zeile fuer ein verknuepftes Playbook (Icon + Name + v).
function PlaybookRow({
  name,
  href,
  version,
}: {
  name: string
  href: string
  version?: number
}) {
  return (
    <Link
      to={href}
      data-testid="agent-hierarchy-playbook"
      className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <GitBranch className="size-4 flex-none text-pill-playbook-fg" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate font-medium text-foreground">{name}</span>
      {version !== undefined ? (
        <span className="flex-none text-xs text-muted-foreground tabular-nums">v{version}</span>
      ) : null}
    </Link>
  )
}

/**
 * „Zusammensetzung"-Karte: System-Prompt, Persona und die verknuepften
 * Playbooks des Agenten als klickbare Verweiszeilen (Plan §"Agent-Detail-
 * Page", Design-Handoff „Detail-Redesign"). Reines Read — die Aktionen
 * (Kopieren/Duplizieren/Loeschen) sitzen im DetailHeader eine Ebene drueber.
 */
export function AgentHierarchyView({
  persona,
  template,
  playbooks,
}: AgentHierarchyViewProps) {
  const { t } = useTranslation('agents')
  const wsPath = useWorkspacePath()

  return (
    <Card data-testid="agent-hierarchy">
      <CardContent className="flex flex-col gap-5 pt-6">
        <SectionLabel>{t('hierarchy.title')}</SectionLabel>

        <div className="flex flex-col gap-2">
          {template !== null ? (
            <PrimaryRow
              icon={FileText}
              tone="date"
              caption={t('hierarchy.systemPrompt')}
              name={template.name}
              href={wsPath(`/system-prompts/${template.id}`)}
              version={template.current_version}
              status={template.current_status}
            />
          ) : (
            <div className="flex flex-col gap-1">
              <SectionLabel>{t('hierarchy.systemPrompt')}</SectionLabel>
              <p className="px-2 text-sm text-muted-foreground">{t('hierarchy.notLoaded')}</p>
            </div>
          )}

          {persona !== null ? (
            <PrimaryRow
              icon={Users}
              tone="persona"
              caption={t('hierarchy.persona')}
              name={persona.name}
              href={wsPath(`/personas/${persona.id}`)}
              version={persona.current_version}
              status={persona.current_status}
            />
          ) : (
            <div className="flex flex-col gap-1">
              <SectionLabel>{t('hierarchy.persona')}</SectionLabel>
              <p className="px-2 text-sm text-muted-foreground">{t('hierarchy.notLoaded')}</p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <SectionLabel>
            {playbooks.length === 0
              ? t('hierarchy.noPlaybooks')
              : t('hierarchy.playbooksLinked', { count: playbooks.length })}
          </SectionLabel>
          {playbooks.map((playbook) => (
            <PlaybookRow
              key={playbook.id}
              name={playbook.name}
              href={wsPath(`/playbooks/${playbook.id}`)}
              version={playbook.current_version}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
