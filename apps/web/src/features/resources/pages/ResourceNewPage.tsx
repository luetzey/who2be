import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LanguageSelect } from '@/components/forms/LanguageSelect'
import { Button } from '@/components/ui/button'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

import { ResourceEditorForm } from '../components/ResourceEditorForm'
import { useCreateResource } from '../hooks/useCreateResource'

export function ResourceNewPage() {
  const { t } = useTranslation('resources')
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const [locales, setLocales] = useState<string[]>(['de'])
  const { form, onSubmit, saveError } = useCreateResource(
    (id) => navigate(wsPath(`/resources/${id}`)),
    locales,
  )

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/resources')}>
            <ArrowLeft className="h-4 w-4" />
            {t('list.title')}
          </Link>
        </Button>
        <PageHeader title={t('new.title')} description={t('new.description')} />
        <LanguageSelect value={locales} onChange={setLocales} idBase="resource-lang" />
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
                  {t('new.submit')}
                </Button>
              </div>
            </div>
          }
        />
      </Stack>
    </Container>
  )
}
