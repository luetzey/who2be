import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useParams } from 'react-router-dom'
import { z } from 'zod'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { Persona, PersonaVersion } from '@/api/types'
import { useApi } from '@/api/useApi'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  systemPrompt: z.string().min(1, 'System-Prompt erforderlich.'),
  traits: z.string(),
})

type EditorValues = z.infer<typeof editorSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

export function PersonaDetailPage() {
  const { id } = useParams<{ id: string }>()
  const api = useApi()
  const [persona, setPersona] = useState<Persona | null>(null)
  const [versions, setVersions] = useState<PersonaVersion[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  const form = useForm<EditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: { name: '', description: '', systemPrompt: '', traits: '' },
  })

  const links = usePersonaPlaybooks(id)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoadError(null)
    Promise.all([api.getPersona(id), api.listPersonaVersions(id)])
      .then(([loaded, versionList]) => {
        setPersona(loaded)
        setVersions(versionList)
        form.reset({
          name: loaded.name,
          description: loaded.content.description,
          systemPrompt: loaded.content.system_prompt,
          traits: loaded.content.traits.join(', '),
        })
      })
      .catch((cause: unknown) => setLoadError(describeError(cause)))
  }, [api, id, form])

  useEffect(load, [load])

  if (id === undefined) {
    return <Navigate to="/" replace />
  }
  const personaId = id

  async function onSubmit(values: EditorValues) {
    setStatus(null)
    setSaveError(null)
    try {
      await api.updatePersona(personaId, {
        name: values.name,
        content: {
          description: values.description,
          system_prompt: values.systemPrompt,
          traits: splitList(values.traits),
        },
      })
      setStatus('Gespeichert — neue Version erstellt.')
      load()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
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

          <DataView loading={persona === null && loadError === null} error={loadError}>
            {persona !== null ? (
              <Stack gap="lg">
                <PageHeader
                  title={persona.name}
                  description={`Aktuelle Version: ${persona.current_version}`}
                />

                {saveError !== null ? <ErrorAlert message={saveError} /> : null}
                {status !== null ? (
                  <Alert role="status">
                    <AlertDescription>{status}</AlertDescription>
                  </Alert>
                ) : null}

                <Card>
                  <CardContent className="pt-6">
                    <Form {...form}>
                      <form
                        onSubmit={form.handleSubmit(onSubmit)}
                        className="flex flex-col gap-4"
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
                                <Input required {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="systemPrompt"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>System-Prompt</FormLabel>
                              <FormControl>
                                <Textarea required rows={6} {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="traits"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Eigenschaften (kommagetrennt)</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <div className="flex justify-end">
                          <Button type="submit" disabled={form.formState.isSubmitting}>
                            Speichern (neue Version)
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
                      {links.status !== null ? (
                        <Alert role="status">
                          <AlertDescription>{links.status}</AlertDescription>
                        </Alert>
                      ) : null}
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
