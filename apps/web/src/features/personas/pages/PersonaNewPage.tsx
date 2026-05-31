import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { PersonaEditorForm } from '../components/PersonaEditorForm'
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
        <PersonaEditorForm
          form={form}
          formKey="new"
          initialProfileBlocks={[]}
          onSubmit={onSubmit}
          actions={
            <div className="flex flex-col gap-3">
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
            </div>
          }
        />
      </Stack>
    </Container>
  )
}
