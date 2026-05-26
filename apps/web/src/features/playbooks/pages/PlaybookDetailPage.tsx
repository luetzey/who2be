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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { Playbook, PlaybookVersion } from '@/api/types'
import { useApi } from '@/api/useApi'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.string().min(1, 'Typ erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  body: z.string().min(1, 'Inhalt erforderlich.'),
  tags: z.string(),
  triggers: z.string(),
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

export function PlaybookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const api = useApi()
  const [playbook, setPlaybook] = useState<Playbook | null>(null)
  const [versions, setVersions] = useState<PlaybookVersion[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  const form = useForm<EditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: {
      name: '',
      type: 'workflow',
      description: '',
      body: '',
      tags: '',
      triggers: '',
    },
  })

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoadError(null)
    Promise.all([api.getPlaybook(id), api.listPlaybookVersions(id)])
      .then(([loaded, versionList]) => {
        setPlaybook(loaded)
        setVersions(versionList)
        form.reset({
          name: loaded.name,
          type: loaded.content.type,
          description: loaded.content.description,
          body: loaded.content.body,
          tags: loaded.content.tags.join(', '),
          triggers: loaded.content.triggers ?? '',
        })
      })
      .catch((cause: unknown) => setLoadError(describeError(cause)))
  }, [api, id, form])

  useEffect(load, [load])

  if (id === undefined) {
    return <Navigate to="/playbooks" replace />
  }
  const playbookId = id

  async function onSubmit(values: EditorValues) {
    setStatus(null)
    setSaveError(null)
    try {
      await api.updatePlaybook(playbookId, {
        name: values.name,
        content: {
          description: values.description,
          body: values.body,
          type: values.type,
          tags: splitList(values.tags),
          triggers: values.triggers.trim() === '' ? null : values.triggers.trim(),
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
            <Link to="/playbooks">
              <ArrowLeft className="h-4 w-4" />
              Playbooks
            </Link>
          </Button>

          <DataView loading={playbook === null && loadError === null} error={loadError}>
            {playbook !== null ? (
              <Stack gap="lg">
                <PageHeader
                  title={playbook.name}
                  description={`Aktuelle Version: ${playbook.current_version}`}
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
                          name="type"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Typ</FormLabel>
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
                          name="body"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Inhalt</FormLabel>
                              <FormControl>
                                <Textarea required rows={8} {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="tags"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Tags (kommagetrennt)</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="triggers"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Trigger</FormLabel>
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
              </Stack>
            ) : null}
          </DataView>
        </Stack>
    </Container>
  )
}
