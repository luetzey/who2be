import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { usePlaybookResourceLinks } from '@/hooks/usePlaybookResourceLinks'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { LinkedBlocksList } from '../components/LinkedBlocksList'
import { PlaybookEditorForm } from '../components/PlaybookEditorForm'
import { ResourceBlockLinkPicker } from '../components/ResourceBlockLinkPicker'
import { StatusActionBar } from '../components/StatusActionBar'
import { usePlaybook } from '../hooks/usePlaybook'
import { usePlaybookForm } from '../hooks/usePlaybookForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

export function PlaybookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { playbook, versions, loading, error, reload } = usePlaybook(id)
  const { form, onSubmit, saveError } = usePlaybookForm(playbook, reload)
  const resourceLinks = usePlaybookResourceLinks(id)
  const wsPath = useWorkspacePath()

  const removeLink = (target: { resource_id: string; block_id: string }) => {
    const remaining = resourceLinks.links.filter(
      (link) => !(link.resource_id === target.resource_id && link.block_id === target.block_id),
    )
    void resourceLinks.save(
      remaining.map((link, index) => ({
        resource_id: link.resource_id,
        block_id: link.block_id,
        position: index,
      })),
    )
  }

  if (id === undefined) {
    return <Navigate to={wsPath('/playbooks')} replace />
  }

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/playbooks')}>
            <ArrowLeft className="h-4 w-4" />
            Playbooks
          </Link>
        </Button>

        <DataView loading={loading && playbook === null} error={error}>
          {playbook !== null ? (
            <Stack gap="lg">
              {(() => {
                const activeVersion = versions.find((v) => v.status === 'active')
                const draftVersion = versions.find((v) => v.status === 'draft')
                const reviewVersion = versions.find((v) => v.status === 'review')
                const pendingVersion = draftVersion ?? reviewVersion
                const description =
                  activeVersion !== undefined
                    ? `Aktive Version: v${activeVersion.version}${
                        pendingVersion !== undefined
                          ? ` · Du bearbeitest: v${pendingVersion.version} (${statusLabel(
                              pendingVersion.status ?? 'draft',
                            )})`
                          : ''
                      }`
                    : `Aktuelle Version: ${playbook.current_version}`
                const transitionVersion = pendingVersion
                return (
                  <Stack gap="md">
                    <PageHeader
                      title={playbook.name}
                      description={description}
                      actions={
                        playbook.tags.length > 0 ? (
                          <div className="flex flex-wrap gap-1" aria-label="Tags">
                            {playbook.tags.map((tag) => (
                              <Badge key={tag} variant="secondary">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        ) : undefined
                      }
                    />
                    {transitionVersion !== undefined &&
                    transitionVersion.status !== undefined ? (
                      <StatusActionBar
                        playbookId={playbook.id}
                        version={transitionVersion.version}
                        status={transitionVersion.status}
                        onTransitioned={reload}
                      />
                    ) : null}
                  </Stack>
                )
              })()}
              <PlaybookEditorForm form={form} onSubmit={onSubmit} saveError={saveError} />

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

              <Card>
                <CardHeader>
                  <CardTitle>Verknuepfte Resource-Bloecke</CardTitle>
                </CardHeader>
                <CardContent>
                  <Stack gap="sm">
                    <DataView loading={resourceLinks.loading} error={resourceLinks.error}>
                      <LinkedBlocksList
                        links={resourceLinks.links}
                        onRemove={removeLink}
                        disabled={resourceLinks.saving}
                      />
                    </DataView>
                    <div className="flex justify-end">
                      <ResourceBlockLinkPicker
                        existing={resourceLinks.links}
                        saving={resourceLinks.saving}
                        onSave={resourceLinks.save}
                      />
                    </div>
                  </Stack>
                </CardContent>
              </Card>
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
