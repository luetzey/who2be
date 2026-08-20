import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LanguageSelect } from '@/components/forms/LanguageSelect'
import { Button } from '@/components/ui/button'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { useContentLocaleField } from '@/hooks/useContentLocaleField'

import { PersonaEditorForm } from '../components/PersonaEditorForm'
import { useCreatePersona } from '../hooks/useCreatePersona'

export function PersonaNewPage() {
  const { t } = useTranslation('personas')
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const { locale, setLocale } = useContentLocaleField()
  const { form, onSubmit, saveError } = useCreatePersona(
    (id) => navigate(wsPath(`/personas/${id}`)),
    locale,
  )

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/personas')}>
            <ArrowLeft className="h-4 w-4" />
            {t('list.title')}
          </Link>
        </Button>
        <PageHeader title={t('new.title')} description={t('new.description')} />
        <LanguageSelect value={locale} onChange={setLocale} idBase="persona-lang" />
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
                  data-testid="persona-new-submit"
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
