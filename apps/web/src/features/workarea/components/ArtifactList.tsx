import { FileText, Paperclip, Table2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { ArtifactType, WaArtifact } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EntityCard } from '@/components/data/EntityCard'
import { MetaPill } from '@/components/data/MetaPill'
import { Badge } from '@/components/ui/badge'

import { useWorkAreaArtifacts } from '../hooks/useWorkAreaArtifacts'

const TYPE_ICON: Record<ArtifactType, LucideIcon> = {
  doc: FileText,
  table: Table2,
  blob: Paperclip,
}

interface ArtifactListProps {
  areaId: string
}

export function ArtifactList({ areaId }: ArtifactListProps) {
  const { t, i18n } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const { artifacts, loading, error } = useWorkAreaArtifacts(areaId)

  const formatOccurred = (artifact: WaArtifact): string => {
    // `unknown` heisst: der Zeitpunkt ist nicht bekannt. Ein Datum zu zeigen,
    // das der Server ausdruecklich als unbekannt fuehrt, waere eine Erfindung.
    if (artifact.occurred_precision === 'unknown') return t('artifacts.occurredUnknown')
    const date = new Date(artifact.occurred_at)
    return artifact.occurred_precision === 'day'
      ? date.toLocaleDateString(i18n.language)
      : date.toLocaleString(i18n.language)
  }

  return (
    <DataView
      loading={loading}
      error={error}
      empty={artifacts.length === 0}
      emptyTitle={t('artifacts.emptyTitle')}
      emptyDescription={t('artifacts.emptyDescription')}
    >
      <ul className="flex flex-col gap-3">
        {artifacts.map((artifact) => (
          <li key={artifact.id}>
            <EntityCard
              icon={TYPE_ICON[artifact.type]}
              iconTone="resource"
              title={artifact.title}
              href={wsPath(`/workarea/areas/${areaId}/artifacts/${artifact.id}`)}
              badges={
                <>
                  <Badge variant="outline">{t(`artifacts.type${capitalize(artifact.type)}`)}</Badge>
                  {artifact.sensitivity === 'sensitive' ? (
                    <Badge variant="destructive">{t('artifacts.sensitive')}</Badge>
                  ) : null}
                </>
              }
              meta={
                <>
                  <MetaPill tone="date">{formatOccurred(artifact)}</MetaPill>
                  {artifact.source_system !== null || artifact.source_url !== null ? (
                    <MetaPill tone="muted">
                      {t('artifacts.source', {
                        source: artifact.source_system ?? artifact.source_url,
                      })}
                    </MetaPill>
                  ) : null}
                </>
              }
            />
          </li>
        ))}
      </ul>
    </DataView>
  )
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
