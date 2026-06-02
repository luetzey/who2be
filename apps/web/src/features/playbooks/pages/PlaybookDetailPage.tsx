import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { ResourceLink, VersionStatus } from '@/api/types'
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
import { usePlaybookComposes } from '@/hooks/usePlaybookComposes'
import { usePlaybookResourceLinks } from '@/hooks/usePlaybookResourceLinks'
import { usePlaybookUsages } from '@/hooks/usePlaybookUsages'
import { notify } from '@/lib/feedback'

import { ComposedByList } from '../components/ComposedByList'
import { LinkedBlocksList } from '../components/LinkedBlocksList'
import { PlaybookComposesPicker } from '../components/PlaybookComposesPicker'
import { PlaybookEditorForm } from '../components/PlaybookEditorForm'
import { ResourceBlockLinkPicker } from '../components/ResourceBlockLinkPicker'
import { usePlaybook } from '../hooks/usePlaybook'
import { usePlaybookForm } from '../hooks/usePlaybookForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'
import { splitTriggers } from '../lib/triggers'

export function PlaybookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { playbook, versions, loading, error, reload } = usePlaybook(id)
  const { form, autoSave, initialBodyBlocks, initialBodyFormat } = usePlaybookForm(
    playbook,
    reload,
  )
  const resourceLinks = usePlaybookResourceLinks(id)
  const usages = usePlaybookUsages(id)
  const composition = usePlaybookComposes(id)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [actionBusy, setActionBusy] = useState(false)

  // Ist der Body im BlockNote-Format, sind die Pills im Body die Quelle der
  // Relationen — die separaten Picker werden read-only (Editier-Aktion
  // ausgeblendet), damit es keine zwei konkurrierenden Quellen gibt.
  const bodyIsBlockNote = playbook?.content.body_format === 'blocknote'

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

  const runTransition = async (
    version: number,
    to: VersionStatus,
    successMessage: string,
  ) => {
    if (playbook === null) {
      return
    }
    setActionBusy(true)
    try {
      await autoSave.flush()
      await api.transitionPlaybookVersion(playbook.id, version, to)
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
                const description =
                  activeVersion !== undefined
                    ? `Active: v${activeVersion.version}${
                        draftVersion !== undefined
                          ? ` · Du arbeitest auf Draft v${draftVersion.version}`
                          : reviewVersion !== undefined
                            ? ` · In Review: v${reviewVersion.version}`
                            : ''
                      }`
                    : `Aktuelle Version: v${playbook.current_version} (${statusLabel(
                        playbook.current_status ?? 'draft',
                      )})`
                const triggers = splitTriggers(playbook.triggers ?? null)

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
                    <PageHeader
                      title={playbook.name}
                      description={description}
                      actions={
                        <div className="flex flex-wrap items-center gap-2">
                          {playbook.is_composite === true ? (
                            <Badge variant="secondary">Composite</Badge>
                          ) : null}
                          {playbook.tags.length > 0 ? (
                            <div className="flex flex-wrap gap-1" aria-label="Tags">
                              {playbook.tags.map((tag) => (
                                <Badge key={tag} variant="secondary">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          ) : null}
                        </div>
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
                    <BranchStatus
                      activeVersion={activeVersion?.version}
                      draftVersion={draftVersion?.version}
                      reviewVersion={reviewVersion?.version}
                      inactiveVersion={inactiveCurrent?.version}
                      currentVersion={playbook.current_version}
                      saveState={autoSave}
                      actions={actions}
                    />
                  </Stack>
                )
              })()}
              <PlaybookEditorForm
                form={form}
                formKey={`${playbook.id}-${playbook.current_version}`}
                initialBodyBlocks={initialBodyBlocks}
                initialBodyFormat={initialBodyFormat}
                composesChildren={composition.children}
                resourceLinks={resourceLinks.links}
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
                        onRemove={bodyIsBlockNote ? undefined : removeLink}
                        disabled={resourceLinks.saving || bodyIsBlockNote}
                      />
                    </DataView>
                    {bodyIsBlockNote ? (
                      <p className="text-xs text-muted-foreground">
                        Resource-Verknüpfungen werden im BlockNote-Body als Pills
                        gepflegt — bearbeite sie dort.
                      </p>
                    ) : (
                      <div className="flex justify-end">
                        <ResourceBlockLinkPicker
                          existing={resourceLinks.links}
                          saving={resourceLinks.saving}
                          onSave={resourceLinks.save}
                        />
                      </div>
                    )}
                  </Stack>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Sub-Playbooks (Composes)</CardTitle>
                </CardHeader>
                <CardContent>
                  <Stack gap="sm">
                    <DataView loading={composition.loading} error={composition.error}>
                      {composition.children.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          Keine Sub-Playbooks verknüpft. Dieses Playbook ist atomar.
                        </p>
                      ) : (
                        <ol className="flex flex-col gap-1" aria-label="Sub-Playbooks">
                          {composition.children.map((child, index) => (
                            <li
                              key={child.id}
                              className="flex items-center gap-2 text-sm"
                            >
                              <span className="w-5 text-right text-xs text-muted-foreground">
                                {index + 1}.
                              </span>
                              <Link
                                to={wsPath(`/playbooks/${child.id}`)}
                                className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                              >
                                {child.name}
                              </Link>
                              {child.is_composite === true ? (
                                <Badge variant="outline" className="text-xs">
                                  Composite
                                </Badge>
                              ) : null}
                            </li>
                          ))}
                        </ol>
                      )}
                    </DataView>
                    {bodyIsBlockNote ? (
                      <p className="text-xs text-muted-foreground">
                        Sub-Playbooks werden im BlockNote-Body als Pills
                        gepflegt — bearbeite sie dort.
                      </p>
                    ) : (
                      <div className="flex justify-end">
                        <PlaybookComposesPicker
                          currentPlaybookId={playbook.id}
                          existing={composition.children}
                          saving={composition.saving}
                          onSave={composition.save}
                        />
                      </div>
                    )}
                  </Stack>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Verwendet als Sub-Playbook in</CardTitle>
                </CardHeader>
                <CardContent>
                  <ComposedByList parents={composition.parents} />
                </CardContent>
              </Card>
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
