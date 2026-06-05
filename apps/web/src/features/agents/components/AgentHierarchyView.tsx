import { Bot, FileText, GitBranch, Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { Agent, Persona, Playbook, SystemPromptTemplate } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface AgentHierarchyViewProps {
  agent: Agent
  persona: Persona | null
  template: SystemPromptTemplate | null
  playbooks: Playbook[]
}

/**
 * Rendert den Tree Agent → Template + Persona → Playbooks (Plan §"Agent-
 * Detail-Page"). Keine eigenen Aktions-Buttons — der CopyPromptButton
 * sitzt eine Ebene drueber, damit die Hierarchie reines Read bleibt.
 */
export function AgentHierarchyView({
  agent,
  persona,
  template,
  playbooks,
}: AgentHierarchyViewProps) {
  const { t } = useTranslation('agents')

  return (
    <Card data-testid="agent-hierarchy">
      <CardHeader className="flex flex-row items-center gap-2">
        <Bot className="h-5 w-5 text-muted-foreground" />
        <div className="flex-1">
          <CardTitle className="text-base">{agent.name}</CardTitle>
          {agent.description ? (
            <p className="text-sm text-muted-foreground">{agent.description}</p>
          ) : null}
        </div>
        <Badge variant={agent.status === 'enabled' ? 'default' : 'outline'}>
          {agent.status === 'enabled' ? t('status.enabled') : t('status.disabled')}
        </Badge>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-3 border-l-2 border-muted pl-4">
          <li>
            <div className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{t('hierarchy.templateLabel')}</span>
              {template !== null ? (
                <>
                  <span>{template.name}</span>
                  <Badge variant="outline">v{template.current_version}</Badge>
                </>
              ) : (
                <span className="text-muted-foreground">{t('hierarchy.notLoaded')}</span>
              )}
            </div>
          </li>
          <li>
            <div className="flex items-center gap-2 text-sm">
              <Users className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{t('hierarchy.personaLabel')}</span>
              {persona !== null ? (
                <>
                  <span>{persona.name}</span>
                  <Badge variant="outline">v{persona.current_version}</Badge>
                </>
              ) : (
                <span className="text-muted-foreground">{t('hierarchy.notLoaded')}</span>
              )}
            </div>
            <ul className="mt-2 flex flex-col gap-1 border-l border-muted pl-4 text-sm">
              {playbooks.length === 0 ? (
                <li className="text-muted-foreground">{t('hierarchy.noPlaybooks')}</li>
              ) : (
                playbooks.map((playbook) => (
                  <li
                    key={playbook.id}
                    className="flex items-center gap-2"
                    data-testid="agent-hierarchy-playbook"
                  >
                    <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{playbook.name}</span>
                    <Badge variant="outline">v{playbook.current_version}</Badge>
                  </li>
                ))
              )}
            </ul>
          </li>
        </ol>
      </CardContent>
    </Card>
  )
}
