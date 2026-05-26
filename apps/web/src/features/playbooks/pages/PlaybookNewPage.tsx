import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { AppShell } from '@/components/layout/AppShell'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'

const playbookSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.string().min(1, 'Typ erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  body: z.string().min(1, 'Inhalt erforderlich.'),
  tags: z.string(),
  triggers: z.string(),
})

type PlaybookValues = z.infer<typeof playbookSchema>

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export function PlaybookNewPage() {
  const api = useApi()
  const navigate = useNavigate()
  const { signOut } = useSession()
  const [error, setError] = useState<string | null>(null)

  const form = useForm<PlaybookValues>({
    resolver: zodResolver(playbookSchema),
    defaultValues: {
      name: '',
      type: 'workflow',
      description: '',
      body: '',
      tags: '',
      triggers: '',
    },
  })

  async function onSubmit(values: PlaybookValues) {
    setError(null)
    try {
      const created = await api.createPlaybook({
        name: values.name,
        content: {
          description: values.description,
          body: values.body,
          type: values.type,
          tags: splitList(values.tags),
          triggers: values.triggers.trim() === '' ? null : values.triggers.trim(),
        },
      })
      navigate(`/playbooks/${created.id}`)
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
        <PageHeader title="Neues Playbook" description="Lege ein neues Playbook an." />
        <Card>
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
                    Anlegen
                  </Button>
                </div>
                {error !== null ? <ErrorAlert message={error} /> : null}
              </form>
            </Form>
          </CardContent>
        </Card>
      </Container>
    </AppShell>
  )
}
