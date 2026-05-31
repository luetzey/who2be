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
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'
import { notify } from '@/lib/feedback'

import { PersonaEditorForm } from '../components/PersonaEditorForm'
import { PlaybookLinkItem } from '../components/PlaybookLinkItem'
import { usePersona } from '../hooks/usePersona'
import { usePersonaForm } from '../hooks/usePersonaForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

export function PersonaDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { persona, versions, loading, error, reload } = usePersona(id)
  const { form, autoSave } = usePersonaForm(persona, reload)
  const links = usePersonaPlaybooks(id)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [actionBusy, setActionBusy] = useState(false)

  if (id === undefined) {
    return <Navigate to={wsPath('/personas')} replace />
  }

  const runTransition = async (
    version: number,
    to: VersionStatus,
    successMessage: string,
  ) => {
    if (persona === null) {
      return
    }
    setActionBusy(true)
    try {
      // Vor jeder Branch-Aktion erst den Auto-Save flushen — sonst wuerden
      // pending Edits verworfen, wenn der Server-Reload den Draft frisch
      // liefert.
      await autoSave.flush()
      await api.transitionPersonaVersion(persona.id, version, to)
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
          <Link to={wsPath('/personas')}>
            <ArrowLeft className="h-4 w-4" />
            Personae
          </Link>
        </Button>

        <DataView loading={loading && persona === null} error={error}>
          {persona !== null ? (
            <Stack gap="lg">
              {(() => {
                const activeVersion = versions.find((v) => v.status === 'active')
                const draftVersion = versions.find((v) => v.status === 'draft')
                const reviewVersion = versions.find((v) => v.status === 'review')
                const inactiveCurrent =
                  activeVersion === undefined
                    ? versions.find(
                        (v) =>
                          v.version === persona.current_version &&
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
                    : `Aktuelle Version: v${persona.current_version} (${statusLabel(
                        persona.current_status ?? 'draft',
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
                    <PageHeader title={persona.name} description={description} />
                    <BranchStatus
                      activeVersion={activeVersion?.version}
                      draftVersion={draftVersion?.version}
                      reviewVersion={reviewVersion?.version}
                      inactiveVersion={inactiveCurrent?.version}
                      currentVersion={persona.current_version}
                      saveState={autoSave}
                      actions={actions}
                    />
                  </Stack>
                )
              })()}
              <PersonaEditorForm
                form={form}
                formKey={`${persona.id}-${persona.current_version}`}
                initialProfileBlocks={persona.content.content?.blocks ?? []}
                legacySystemPrompt={persona.content.system_prompt}
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
                  <CardTitle>Verknüpfte Playbooks</CardTitle>
                </CardHeader>
                <CardContent>
                  <Stack gap="sm">
                    <DataView
                      loading={links.loading}
                      error={links.error}
                      empty={!links.loading && links.playbooks.length === 0}
                      emptyTitle="Keine Playbooks vorhanden."
                    >
                      <ul className="flex flex-col gap-2">
                        {links.playbooks.map((playbook) => (
                          <PlaybookLinkItem
                            key={playbook.id}
                            id={playbook.id}
                            name={playbook.name}
                            checked={links.linkedIds.includes(playbook.id)}
                            onToggle={() => links.toggle(playbook.id)}
                          />
                        ))}
                      </ul>
                    </DataView>
                    <div className="flex justify-end">
                      <Button
                        type="button"
                        onClick={() => void links.save()}
                        disabled={links.saving || links.loading}
                      >
                        Verknüpfungen speichern
                      </Button>
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
