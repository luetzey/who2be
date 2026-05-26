import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useParams } from 'react-router-dom'
import { z } from 'zod'

import { AppShell } from '@/components/layout/AppShell'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataList } from '@/components/data/DataList'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { Playbook, PlaybookVersion } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'

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
  const { signOut } = useSession()
  const [playbook, setPlaybook] = useState<Playbook | null>(null)
  const [versions, setVersions] = useState<PlaybookVersion[]>([])
  const [error, setError] = useState<string | null>(null)
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
    setError(null)
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
      .catch((cause: unknown) => setError(describeError(cause)))
  }, [api, id, form])

  useEffect(load, [load])

  if (id === undefined) {
    return <Navigate to="/playbooks" replace />
  }
  const playbookId = id

  async function onSubmit(values: EditorValues) {
    setStatus(null)
    setError(null)
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
      setError(describeError(cause))
    }
  }

  return (
    <AppShell onSignOut={() => void signOut()}>
      <Container>
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/playbooks">
            <ArrowLeft className="h-4 w-4" />
            Playbooks
          </Link>
        </Button>

        {error !== null ? (
          <div className="mb-4">
            <ErrorAlert message={error} />
          </div>
        ) : null}
        {status !== null ? (
          <Alert role="status" className="mb-4">
            <AlertDescription>{status}</AlertDescription>
          </Alert>
        ) : null}

        {playbook === null ? (
          <LoadingState />
        ) : (
          <>
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

            <Card className="mb-6">
              <CardContent className="pt-6">
                <Form {...form}>
                  <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                <CardTitle>
                  <h2 className="text-lg font-semibold tracking-tight">Versionen</h2>
                </CardTitle>
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
          </>
        )}
      </Container>
    </AppShell>
  )
}
