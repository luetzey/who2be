import { FolderLock, FolderOpen } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { Agent, WorkArea } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EntityCard } from '@/components/data/EntityCard'
import { MetaPill } from '@/components/data/MetaPill'
import { Badge } from '@/components/ui/badge'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { useAgents } from '@/hooks/useAgents'

import { NewWorkAreaDialog } from '../components/NewWorkAreaDialog'
import { useWorkAreas } from '../hooks/useWorkAreas'

// Bestandstoene wiederverwenden statt neue Pill-Tinten einzufuehren: geteilte
// Bereiche lesen sich wie ein Katalog, private wie ein Einzel-Besitz.
function toneFor(area: WorkArea) {
  return area.scope === 'shared' ? ('catalog' as const) : ('persona' as const)
}

export function AreasPage() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const { areas, loading, error, reload } = useWorkAreas()
  // Nur fuer die Namensaufloesung der Besitzer privater Bereiche. Ein Fehler
  // hier darf die Bereichs-Liste nicht kippen — ohne Namen zeigen wir die
  // Karte trotzdem, nur ohne Agenten-Pill.
  const { agents } = useAgents()

  const agentName = (id: string): string | null =>
    agents.find((agent: Agent) => agent.id === id)?.name ?? null

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('list.title')}
          description={t('list.description')}
          actions={<NewWorkAreaDialog onCreated={reload} />}
        />
        <DataView
          loading={loading}
          error={error}
          empty={areas.length === 0}
          emptyTitle={t('list.emptyTitle')}
          emptyDescription={t('list.emptyDescription')}
        >
          <ul className="flex flex-col gap-3">
            {areas.map((area) => {
              const owner = area.owner_agent_id !== null ? agentName(area.owner_agent_id) : null
              return (
                <li key={area.id}>
                  <EntityCard
                    icon={area.scope === 'shared' ? FolderOpen : FolderLock}
                    iconTone={toneFor(area)}
                    title={area.name}
                    href={wsPath(`/workarea/areas/${area.id}`)}
                    badges={
                      <Badge variant="secondary">
                        {area.scope === 'shared' ? t('list.scopeShared') : t('list.scopePrivate')}
                      </Badge>
                    }
                    meta={
                      <>
                        {area.owner_agent_id !== null ? (
                          <MetaPill tone="persona">
                            {owner !== null
                              ? t('list.ownerAgent', { name: owner })
                              : t('list.ownerUnknown')}
                          </MetaPill>
                        ) : null}
                        <MetaPill tone="date">
                          {area.retention_days !== null
                            ? t('list.retention', { days: area.retention_days })
                            : t('list.retentionUnlimited')}
                        </MetaPill>
                      </>
                    }
                  />
                </li>
              )
            })}
          </ul>
        </DataView>
      </Stack>
    </Container>
  )
}
