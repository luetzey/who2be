import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { notify } from '@/lib/feedback'

import { PlaceholderHelp } from '../components/PlaceholderHelp'

const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  body: z.string().min(1, 'Body erforderlich.'),
})

type CreateValues = z.infer<typeof createSchema>

export function SystemPromptNewPage() {
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', description: '', body: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createSystemPromptTemplate({
        name: values.name,
        content: { description: values.description, body: values.body },
      })
      notify.success('Template angelegt.')
      navigate(wsPath(`/system-prompts/${created.id}`))
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : 'Unbekannter Fehler.')
    }
  })

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/system-prompts')}>
            <ArrowLeft className="h-4 w-4" />
            System-Prompts
          </Link>
        </Button>
        <PageHeader
          title="Neues Template"
          description="Lege ein wiederverwendbares System-Prompt-Template an."
        />
        <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
          <Card>
            <CardContent className="pt-6">
              <Form {...form}>
                <form onSubmit={onSubmit} className="flex flex-col gap-4">
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
                  <FormField
                    control={form.control}
                    name="body"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Body</FormLabel>
                        <FormControl>
                          <Textarea
                            required
                            rows={16}
                            className="font-mono text-sm"
                            placeholder="Du bist {{ persona.name }} — …"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  {saveError !== null ? <ErrorAlert message={saveError} /> : null}
                  <div className="flex justify-end">
                    <Button
                      type="submit"
                      variant="brand"
                      disabled={form.formState.isSubmitting}
                    >
                      Anlegen
                    </Button>
                  </div>
                </form>
              </Form>
            </CardContent>
          </Card>
          <aside
            aria-label="Placeholder-Hilfe"
            className="lg:sticky lg:top-4 lg:self-start"
          >
            <PlaceholderHelp compact />
          </aside>
        </div>
      </Stack>
    </Container>
  )
}
