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
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { ResourceEditor } from '../components/ResourceEditor'
import { StatusActionBar } from '../components/StatusActionBar'
import { useResource } from '../hooks/useResource'
import { useResourceForm } from '../hooks/useResourceForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

export function ResourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { resource, versions, loading, error, reload } = useResource(id)
  const { form, setBlocks, onSubmit, saveError } = useResourceForm(resource, reload)
  const wsPath = useWorkspacePath()

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
                    : `Aktuelle Version: ${resource.current_version}`
                return (
                  <Stack gap="md">
                    <PageHeader title={resource.name} description={description} />
                    {pendingVersion !== undefined && pendingVersion.status !== undefined ? (
                      <StatusActionBar
                        resourceId={resource.id}
                        version={pendingVersion.version}
                        status={pendingVersion.status}
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
                          disabled={form.formState.isSubmitting}
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
