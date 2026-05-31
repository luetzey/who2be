import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { BranchStatus } from '@/components/data/BranchStatus'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useResourceUsages } from '@/hooks/useResourceUsages'

import { ResourceEditorForm } from '../components/ResourceEditorForm'
import { StatusActionBar } from '../components/StatusActionBar'
import { useResource } from '../hooks/useResource'
import { useResourceForm } from '../hooks/useResourceForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

export function ResourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { resource, versions, loading, error, reload } = useResource(id)
  const { form, autoSave } = useResourceForm(resource)
  const usages = useResourceUsages(id)
  const wsPath = useWorkspacePath()

  if (id === undefined) {
    return <Navigate to={wsPath('/resources')} replace />
  }

  const draftVersion = versions.find((v) => v.status === 'draft')
  const reviewVersion = versions.find((v) => v.status === 'review')
  const activeVersion = versions.find((v) => v.status === 'active')
  const inactiveCurrent =
    activeVersion === undefined
      ? versions.find(
          (v) =>
            v.version === resource?.current_version && v.status === 'inactive',
        )
      : undefined

  const promotableVersion = reviewVersion ?? draftVersion

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/resources')}>
            <ArrowLeft className="h-4 w-4" />
            Resources
          </Link>
        </Button>

        <DataView loading={loading && resource === null} error={error}>
          {resource !== null ? (
            <Stack gap="lg">
              {(() => {
                const description =
                  activeVersion !== undefined
                    ? `Active: v${activeVersion.version}${
                        draftVersion !== undefined
                          ? ` · Du arbeitest auf Draft v${draftVersion.version}`
                          : reviewVersion !== undefined
                            ? ` · In Review: v${reviewVersion.version}`
                            : ''
                      }`
                    : `Aktuelle Version: v${resource.current_version} (${statusLabel(
                        resource.current_status ?? 'draft',
                      )})`
                return (
                  <Stack gap="sm">
                    <PageHeader title={resource.name} description={description} />
                    <BranchStatus
                      activeVersion={activeVersion?.version}
                      draftVersion={draftVersion?.version}
                      reviewVersion={reviewVersion?.version}
                      inactiveVersion={inactiveCurrent?.version}
                      currentVersion={resource.current_version}
                      saveState={autoSave}
                      actions={[]}
                    />
                    {promotableVersion !== undefined ? (
                      <StatusActionBar
                        resourceId={resource.id}
                        version={promotableVersion.version}
                        status={promotableVersion.status ?? 'draft'}
                        onTransitioned={reload}
                      />
                    ) : null}
                    {inactiveCurrent !== undefined ? (
                      <StatusActionBar
                        resourceId={resource.id}
                        version={inactiveCurrent.version}
                        status="inactive"
                        onTransitioned={reload}
                      />
                    ) : null}
                  </Stack>
                )
              })()}

              <ResourceEditorForm
                form={form}
                formKey={`${resource.id}-${resource.current_version}`}
                initialBodyBlocks={resource.content.blocks ?? []}
              />

              <Card>
                <CardHeader>
                  <CardTitle>Verlinkt in</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataView
                    loading={usages.loading}
                    error={usages.error}
                    empty={!usages.loading && usages.usages.length === 0}
                    emptyTitle="Noch in keinem Playbook verwendet"
                    emptyDescription="Verlinke einen Heading-Block in einem Playbook, um diese Resource sichtbar zu machen."
                  >
                    <DataList
                      items={usages.usages}
                      getKey={(usage) => usage.playbook_id}
                      renderItem={(usage) => (
                        <span className="flex items-center justify-between gap-3">
                          <Link
                            to={wsPath(`/playbooks/${usage.playbook_id}`)}
                            className="truncate"
                          >
                            {usage.playbook_name}
                          </Link>
                          <Badge variant="secondary">
                            {usage.block_count}{' '}
                            {usage.block_count === 1 ? 'Block' : 'Bloecke'}
                          </Badge>
                        </span>
                      )}
                    />
                  </DataView>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Versionen</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataList
                    items={versions}
                    getKey={(version) => String(version.version)}
                    renderItem={(version) => (
                      <span className="flex items-center justify-between gap-3">
                        <span>
                          v{version.version} —{' '}
                          {new Date(version.created_at).toLocaleString()}
                        </span>
                        {version.status !== undefined ? (
                          <Badge variant={statusBadgeVariant(version.status)}>
                            {statusLabel(version.status)}
                          </Badge>
                        ) : null}
                      </span>
                    )}
                  />
                </CardContent>
              </Card>
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
