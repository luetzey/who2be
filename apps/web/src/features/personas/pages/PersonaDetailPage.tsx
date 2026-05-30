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
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { PersonaEditorForm } from '../components/PersonaEditorForm'
import { PlaybookLinkItem } from '../components/PlaybookLinkItem'
import { StatusActionBar } from '../components/StatusActionBar'
import { usePersona } from '../hooks/usePersona'
import { usePersonaForm } from '../hooks/usePersonaForm'
import { statusBadgeVariant, statusLabel } from '../lib/status'

export function PersonaDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { persona, versions, loading, error, reload } = usePersona(id)
  const { form, onSubmit, saveError } = usePersonaForm(persona, reload)
  const links = usePersonaPlaybooks(id)
  const wsPath = useWorkspacePath()

  if (id === undefined) {
    return <Navigate to={wsPath('/personas')} replace />
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
                // Inaktive current_version → Bar zeigt "Reaktivieren als Draft"
                // (Phase 3-C, F-02). Wenn es einen Active gibt, ist die
                // inaktive Version nicht aktuell — kein Reactivate-Anker.
                const inactiveCurrent =
                  activeVersion === undefined
                    ? versions.find(
                        (v) =>
                          v.version === persona.current_version &&
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
                    : `Aktuelle Version: ${persona.current_version}`
                return (
                  <Stack gap="md">
                    <PageHeader title={persona.name} description={description} />
                    {actionableVersion !== undefined &&
                    actionableVersion.status !== undefined ? (
                      <StatusActionBar
                        personaId={persona.id}
                        version={actionableVersion.version}
                        status={actionableVersion.status}
                        onTransitioned={reload}
                      />
                    ) : null}
                  </Stack>
                )
              })()}
              <PersonaEditorForm
                form={form}
                onSubmit={onSubmit}
                saveError={saveError}
                formKey={`${persona.id}-${persona.current_version}`}
                initialProfileBlocks={persona.content.content?.blocks ?? []}
                initialSystemPrompt={persona.content.system_prompt}
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
