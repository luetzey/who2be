import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { ResourceEditor } from '../components/ResourceEditor'
import { StatusActionBar } from '../components/StatusActionBar'
import { useResource } from '../hooks/useResource'
import { useResourceForm } from '../hooks/useResourceForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

import { useResourceUsages } from '@/hooks/useResourceUsages'

export function ResourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { resource, versions, loading, error, reload } = useResource(id)
  const { form, setBlocks, onSubmit, saveError } = useResourceForm(resource, reload)
  const usages = useResourceUsages(id)
  const wsPath = useWorkspacePath()
  // Viewer dürfen nur lesen (ADR-0023) — Save bleibt gesperrt.
  const isViewer = useCurrentWorkspaceRole() === 'viewer'

  if (id === undefined) {
    return <Navigate to={wsPath('/resources')} replace />
  }

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
                const activeVersion = versions.find((v) => v.status === 'active')
                const draftVersion = versions.find((v) => v.status === 'draft')
                const reviewVersion = versions.find((v) => v.status === 'review')
                const inactiveCurrent =
                  activeVersion === undefined
                    ? versions.find(
                        (v) =>
                          v.version === resource.current_version &&
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
                    : `Aktuelle Version: ${resource.current_version}`
                return (
                  <Stack gap="md">
                    <PageHeader title={resource.name} description={description} />
                    {actionableVersion !== undefined &&
                    actionableVersion.status !== undefined ? (
                      <StatusActionBar
                        resourceId={resource.id}
                        version={actionableVersion.version}
                        status={actionableVersion.status}
                        onTransitioned={reload}
                      />
                    ) : null}
                  </Stack>
                )
              })()}

              {saveError !== null ? <ErrorAlert message={saveError} /> : null}
              <Card>
                <CardContent className="pt-6">
                  <Form {...form}>
                    <form onSubmit={onSubmit} className="flex flex-col gap-4">
                      <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Name</FormLabel>
                            <FormControl>
                              <Input required {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="description"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Beschreibung</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <div className="flex flex-col gap-2">
                        <Label htmlFor="resource-editor">Inhalt</Label>
                        <ResourceEditor
                          key={`${resource.id}-${resource.current_version}`}
                          initialBlocks={resource.content.blocks ?? []}
                          onChange={setBlocks}
                        />
                      </div>
                      <div className="flex justify-end">
                        <Button
                          type="submit"
                          variant="brand"
                          disabled={form.formState.isSubmitting || isViewer}
                          title={isViewer ? 'Viewer können Inhalte nur ansehen' : undefined}
                        >
                          Neue Version speichern
                        </Button>
                      </div>
                    </form>
                  </Form>
                </CardContent>
              </Card>

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
                          v{version.version} — {new Date(version.created_at).toLocaleString()}
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
