import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { BranchStatus, type BranchAction } from '@/components/data/BranchStatus'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useResourceUsages } from '@/hooks/useResourceUsages'
import { notify } from '@/lib/feedback'

import { ResourceEditor } from '../components/ResourceEditor'
import { useResource } from '../hooks/useResource'
import { useResourceForm } from '../hooks/useResourceForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

export function ResourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { resource, versions, loading, error, reload } = useResource(id)
  const { form, setBlocks, autoSave } = useResourceForm(resource)
  const usages = useResourceUsages(id)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const isViewer = role === 'viewer'
  const [actionBusy, setActionBusy] = useState(false)

  if (id === undefined) {
    return <Navigate to={wsPath('/resources')} replace />
  }

  const runTransition = async (
    version: number,
    to: VersionStatus,
    successMessage: string,
  ) => {
    if (resource === null) {
      return
    }
    setActionBusy(true)
    try {
      await autoSave.flush()
      await api.transitionResourceVersion(resource.id, version, to)
      notify.success(successMessage)
      reload()
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : 'Aktion fehlgeschlagen.')
    } finally {
      setActionBusy(false)
    }
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

                const canPromote = role === 'admin'
                const actions: BranchAction[] = []
                if (draftVersion !== undefined) {
                  actions.push({
                    key: 'submit',
                    label: 'Draft abschliessen',
                    variant: 'brand',
                    disabled: actionBusy,
                    onClick: () =>
                      void runTransition(
                        draftVersion.version,
                        'review',
                        'Zur Review eingereicht.',
                      ),
                  })
                }
                if (reviewVersion !== undefined) {
                  actions.push({
                    key: 'publish',
                    label: 'Veroeffentlichen',
                    variant: 'brand',
                    disabled: actionBusy || !canPromote,
                    title: canPromote ? undefined : 'Nur Admins koennen aktivieren',
                    onClick: () =>
                      void runTransition(
                        reviewVersion.version,
                        'active',
                        'Version aktiviert.',
                      ),
                  })
                  actions.push({
                    key: 'reject',
                    label: 'Zurueck zu Draft',
                    variant: 'destructive',
                    disabled: actionBusy,
                    onClick: () =>
                      void runTransition(
                        reviewVersion.version,
                        'draft',
                        'Review abgelehnt.',
                      ),
                  })
                }
                if (inactiveCurrent !== undefined) {
                  actions.push({
                    key: 'reactivate',
                    label: 'Reaktivieren als Draft',
                    variant: 'outline',
                    disabled: actionBusy,
                    onClick: () =>
                      void runTransition(
                        inactiveCurrent.version,
                        'draft',
                        'Reaktiviert als Entwurf.',
                      ),
                  })
                }
                return (
                  <Stack gap="md">
                    <PageHeader title={resource.name} description={description} />
                    <BranchStatus
                      activeVersion={activeVersion?.version}
                      draftVersion={draftVersion?.version}
                      reviewVersion={reviewVersion?.version}
                      inactiveVersion={inactiveCurrent?.version}
                      currentVersion={resource.current_version}
                      saveState={autoSave}
                      actions={actions}
                    />
                  </Stack>
                )
              })()}

              <Card>
                <CardContent className="pt-6">
                  <Form {...form}>
                    <form
                      className="flex flex-col gap-4"
                      onSubmit={(event) => event.preventDefault()}
                    >
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
                          editable={!isViewer}
                          onChange={setBlocks}
                        />
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
