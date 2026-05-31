import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { ResourceEditorForm } from '../components/ResourceEditorForm'
import { useCreateResource } from '../hooks/useCreateResource'

export function ResourceNewPage() {
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const { form, onSubmit, saveError } = useCreateResource((id) =>
    navigate(wsPath(`/resources/${id}`)),
  )

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/resources')}>
            <ArrowLeft className="h-4 w-4" />
            Resources
          </Link>
        </Button>
        <PageHeader title="Neue Resource" description="Lege eine neue Resource an." />
        <ResourceEditorForm
          form={form}
          formKey="new"
          initialBodyBlocks={[]}
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
