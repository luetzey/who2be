import { FolderLock, FolderOpen, Info } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Navigate, useParams } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { AreaGrants } from '../components/AreaGrants'
import { ArtifactList } from '../components/ArtifactList'
import { useWorkAreas } from '../hooks/useWorkAreas'

export function AreaDetailPage() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const { areaId } = useParams<{ areaId: string }>()
  // Es gibt keinen Einzel-Endpunkt fuer eine Area; die Liste ist der Weg zum
  // Stammsatz — und sie ist ohnehin durch den Sichtbarkeits-Scope gefiltert,
  // eine unsichtbare Area taucht darin schlicht nicht auf.
  const { areas, loading, error } = useWorkAreas()

  if (areaId === undefined) return <Navigate to={wsPath('/workarea')} replace />

  const area = areas.find((candidate) => candidate.id === areaId) ?? null
  const isShared = area?.scope === 'shared'

  return (
    <Container>
      <DataView
        loading={loading && area === null}
        error={error}
        empty={!loading && area === null}
        emptyTitle={t('detail.notFound')}
      >
        {area !== null ? (
          <Stack gap="lg">
            <Stack gap="sm">
              <DetailHeader
                backHref={wsPath('/workarea')}
                backLabel={t('detail.back')}
                icon={isShared ? FolderOpen : FolderLock}
                iconTone={isShared ? 'catalog' : 'persona'}
                title={area.name}
                badges={
                  <Badge variant="secondary">
                    {isShared ? t('list.scopeShared') : t('list.scopePrivate')}
                  </Badge>
                }
              />
              {!isShared ? (
                <AttentionBanner
                  variant="brand"
                  icon={Info}
                  title={t('detail.privateNoticeTitle')}
                  description={t('detail.privateNoticeDescription')}
                />
              ) : null}
            </Stack>
            {isShared ? (
              <Tabs defaultValue="artifacts">
                <TabsList aria-label={t('detail.tabArtifacts')}>
                  <TabsTrigger value="artifacts">{t('detail.tabArtifacts')}</TabsTrigger>
                  <TabsTrigger value="grants">{t('detail.tabGrants')}</TabsTrigger>
                </TabsList>
                <TabsContent value="artifacts">
                  <ArtifactList areaId={area.id} />
                </TabsContent>
                <TabsContent value="grants">
                  <AreaGrants areaId={area.id} />
                </TabsContent>
              </Tabs>
            ) : (
              // Private Areas sind nicht grantbar (403 `area_forbidden`) — ein
              // Zugriffs-Tab waere hier nur eine Sackgasse.
              <ArtifactList areaId={area.id} />
            )}
          </Stack>
        ) : null}
      </DataView>
    </Container>
  )
}
