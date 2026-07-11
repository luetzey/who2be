import { FileText, GitBranch, Users, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Agent, Persona, Playbook, SystemPromptTemplate } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EntityIcon, type EntityTone } from '@/components/data/EntityIcon'
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

// Eine klickbare Verweiszeile (Icon-Kachel + Name-Link + optionale Version).
function LinkRow({
  icon,
  tone,
  name,
  href,
  version,
  testId,
}: {
  icon: LucideIcon
  tone: EntityTone
  name: string
  href: string
  version?: number
  testId?: string
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/40"
      data-testid={testId}
    >
      <EntityIcon icon={icon} tone={tone} size="sm" />
      <Link
        to={href}
        className="min-w-0 flex-1 truncate rounded-sm font-medium text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {name}
      </Link>
      {version !== undefined ? (
        <span className="flex-none text-xs text-muted-foreground tabular-nums">v{version}</span>
      ) : null}
    </div>
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
          <SectionLabel>{t('hierarchy.systemPrompt')}</SectionLabel>
          {template !== null ? (
            <LinkRow
              icon={FileText}
              tone="date"
              name={template.name}
              href={wsPath(`/system-prompts/${template.id}`)}
              version={template.current_version}
            />
          ) : (
            <p className="px-2 text-sm text-muted-foreground">{t('hierarchy.notLoaded')}</p>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <SectionLabel>{t('hierarchy.persona')}</SectionLabel>
          {persona !== null ? (
            <LinkRow
              icon={Users}
              tone="persona"
              name={persona.name}
              href={wsPath(`/personas/${persona.id}`)}
              version={persona.current_version}
            />
          ) : (
            <p className="px-2 text-sm text-muted-foreground">{t('hierarchy.notLoaded')}</p>
          )}

          <div className="mt-1 flex flex-col gap-1 border-l border-muted pl-3">
            <div className="px-2 text-xs text-muted-foreground">
              {playbooks.length === 0
                ? t('hierarchy.noPlaybooks')
                : t('hierarchy.playbooksLinked', { count: playbooks.length })}
            </div>
            {playbooks.map((playbook) => (
              <LinkRow
                key={playbook.id}
                testId="agent-hierarchy-playbook"
                icon={GitBranch}
                tone="playbook"
                name={playbook.name}
                href={wsPath(`/playbooks/${playbook.id}`)}
                version={playbook.current_version}
              />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
