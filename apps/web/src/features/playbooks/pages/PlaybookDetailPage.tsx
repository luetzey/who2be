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
import type { ResourceLink } from '@/api/types'
import { usePlaybookResourceLinks } from '@/hooks/usePlaybookResourceLinks'
import { usePlaybookUsages } from '@/hooks/usePlaybookUsages'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { LinkedBlocksList } from '../components/LinkedBlocksList'
import { PlaybookEditorForm } from '../components/PlaybookEditorForm'
import { ResourceBlockLinkPicker } from '../components/ResourceBlockLinkPicker'
import { StatusActionBar } from '../components/StatusActionBar'
import { usePlaybook } from '../hooks/usePlaybook'
import { usePlaybookForm } from '../hooks/usePlaybookForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'
import { splitTriggers } from '../lib/triggers'

export function PlaybookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { playbook, versions, loading, error, reload } = usePlaybook(id)
  const { form, onSubmit, saveError, initialBodyBlocks } = usePlaybookForm(playbook, reload)
  const resourceLinks = usePlaybookResourceLinks(id)
  const usages = usePlaybookUsages(id)
  const wsPath = useWorkspacePath()

  const removeLink = (target: ResourceLink) => {
    const remaining = resourceLinks.links.filter(
      (link) =>
        !(
          link.resource_id === target.resource_id &&
          link.block_id === target.block_id &&
          (link.link_scope ?? 'block') === (target.link_scope ?? 'block')
        ),
    )
    void resourceLinks.save(
      remaining.map((link, index) => ({
        resource_id: link.resource_id,
        block_id: link.block_id,
        position: index,
        link_scope: link.link_scope ?? 'block',
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
                const inactiveCurrent =
                  activeVersion === undefined
                    ? versions.find(
                        (v) =>
                          v.version === playbook.current_version &&
                          v.status === 'inactive',
                      )
                    : undefined
                const actionableVersion =
                  draftVersion ?? reviewVersion ?? inactiveCurrent
                const description =
                  activeVersion !== undefined
                    ? `Aktive Version: v${activeVersion.version}${
                        actionableVersion !== undefined
                          ? ` · Du bearbeitest: v${actionableVersion.version} (${statusLabel(
                              actionableVersion.status ?? 'draft',
                            )})`
                          : ''
                      }`
                    : `Aktuelle Version: ${playbook.current_version}`
                const triggers = splitTriggers(playbook.triggers ?? null)
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
                    {triggers.length > 0 ? (
                      <div
                        className="flex flex-wrap items-center gap-2"
                        role="list"
                        aria-label="Trigger-Liste"
                      >
                        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                          Trigger
                        </span>
                        {triggers.map((trigger) => (
                          <Badge key={trigger} variant="outline" role="listitem">
                            {trigger}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                    {actionableVersion !== undefined &&
                    actionableVersion.status !== undefined ? (
                      <StatusActionBar
                        playbookId={playbook.id}
                        version={actionableVersion.version}
                        status={actionableVersion.status}
                        onTransitioned={reload}
                      />
                    ) : null}
                  </Stack>
                )
              })()}
              <PlaybookEditorForm
                form={form}
                onSubmit={onSubmit}
                saveError={saveError}
                formKey={`${playbook.id}-${playbook.current_version}`}
                initialBodyBlocks={initialBodyBlocks}
              />

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
                  <CardTitle>Verwendet in</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataView
                    loading={usages.loading}
                    error={usages.error}
                    empty={!usages.loading && usages.usages.length === 0}
                    emptyTitle="Noch in keiner Persona verwendet"
                    emptyDescription="Verknuepfe dieses Playbook im Persona-Editor, um es einer Persona zuzuweisen."
                  >
                    <DataList
                      items={usages.usages}
                      getKey={(usage) => usage.persona_id}
                      renderItem={(usage) => (
                        <Link
                          to={wsPath(`/personas/${usage.persona_id}`)}
                          className="block truncate"
                        >
                          {usage.persona_name}
                        </Link>
                      )}
                    />
                  </DataView>
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
