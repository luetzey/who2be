import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { PlaybookEditorForm } from '../components/PlaybookEditorForm'
import { useCreatePlaybook } from '../hooks/useCreatePlaybook'

export function PlaybookNewPage() {
  const { t } = useTranslation('playbooks')
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const { form, onSubmit, saveError } = useCreatePlaybook((id) =>
    navigate(wsPath(`/playbooks/${id}`)),
  )

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/playbooks')}>
            <ArrowLeft className="h-4 w-4" />
            {t('detail.back')}
          </Link>
        </Button>
        <PageHeader title={t('new.title')} description={t('new.description')} />
        <PlaybookEditorForm
          form={form}
          formKey="new-playbook"
          initialBodyBlocks={[]}
          onSubmit={onSubmit}
          actions={
            <Stack gap="sm">
              {saveError !== null ? <ErrorAlert message={saveError} /> : null}
              <div className="flex justify-end">
                <Button
                  type="submit"
                  variant="brand"
                  disabled={form.formState.isSubmitting}
                >
                  {t('form.createButton')}
                </Button>
              </div>
            </Stack>
          }
        />
      </Stack>
    </Container>
  )
}
