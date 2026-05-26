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

const personaSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  systemPrompt: z.string().min(1, 'System-Prompt erforderlich.'),
  traits: z.string(),
})

type PersonaValues = z.infer<typeof personaSchema>

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export function PersonaNewPage() {
  const api = useApi()
  const navigate = useNavigate()
  const { signOut } = useSession()
  const [error, setError] = useState<string | null>(null)

  const form = useForm<PersonaValues>({
    resolver: zodResolver(personaSchema),
    defaultValues: { name: '', description: '', systemPrompt: '', traits: '' },
  })

  async function onSubmit(values: PersonaValues) {
    setError(null)
    try {
      const created = await api.createPersona({
        name: values.name,
        content: {
          description: values.description,
          system_prompt: values.systemPrompt,
          traits: splitList(values.traits),
        },
      })
      navigate(`/personas/${created.id}`)
    } catch (cause) {
      setError(describeError(cause))
    }
  }

  return (
    <AppShell onSignOut={() => void signOut()}>
      <Container>
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/">
            <ArrowLeft className="h-4 w-4" />
            Personae
          </Link>
        </Button>
        <PageHeader title="Neue Persona" description="Lege eine neue Persona-Version an." />
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
