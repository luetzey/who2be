import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'

import { PersonaEditorForm } from '../components/PersonaEditorForm'
import { usePersona } from '../hooks/usePersona'
import { usePersonaForm } from '../hooks/usePersonaForm'

export function PersonaDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { persona, versions, loading, error, reload } = usePersona(id)
  const { form, onSubmit, saveError } = usePersonaForm(persona, reload)
  const links = usePersonaPlaybooks(id)

  if (id === undefined) {
    return <Navigate to="/" replace />
  }

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to="/">
            <ArrowLeft className="h-4 w-4" />
            Personae
          </Link>
        </Button>

        <DataView loading={loading && persona === null} error={error}>
          {persona !== null ? (
            <Stack gap="lg">
              <PageHeader
                title={persona.name}
                description={`Aktuelle Version: ${persona.current_version}`}
              />
              <PersonaEditorForm form={form} onSubmit={onSubmit} saveError={saveError} />

              <Card>
                <CardHeader>
                  <CardTitle>Versionen</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataList
                    items={versions}
                    getKey={(version) => String(version.version)}
                    renderItem={(version) => (
                      <span>
                        v{version.version} — {new Date(version.created_at).toLocaleString()}
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
                          <li key={playbook.id}>
                            <label className="flex items-center gap-2 text-sm">
                              <Checkbox
                                checked={links.linkedIds.includes(playbook.id)}
                                onChange={() => links.toggle(playbook.id)}
                              />
                              {playbook.name}
                            </label>
                          </li>
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
