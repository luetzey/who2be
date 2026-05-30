import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { useCreatePersona } from '../hooks/useCreatePersona'

export function PersonaNewPage() {
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const { form, onSubmit, saveError } = useCreatePersona((id) =>
    navigate(wsPath(`/personas/${id}`)),
  )

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/personas')}>
            <ArrowLeft className="h-4 w-4" />
            Personae
          </Link>
        </Button>
        <PageHeader title="Neue Persona" description="Lege eine neue Persona-Version an." />
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
                        <Input required {...field} />
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
      </Stack>
    </Container>
  )
}
