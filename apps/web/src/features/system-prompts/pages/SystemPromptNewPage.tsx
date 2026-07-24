import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { SystemPromptEditor } from '@/components/editor/system-prompt/SystemPromptEditor'
import type { SystemPromptBlock } from '@/components/editor/system-prompt/SystemPromptEditor'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LanguageSelect } from '@/components/forms/LanguageSelect'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { useContentLocaleField } from '@/hooks/useContentLocaleField'
import { notify } from '@/lib/feedback'

import { PlaceholderHelp } from '../components/PlaceholderHelp'

// Track B (Nur-BlockNote): Templates sind immer BlockNote.
// body-Validierung: kein min(1) — ein leeres BlockNote-Dok ist valid.
const createSchema = z.object({
  name: z.string().min(1, i18n.t('common:validation.nameRequired')),
  description: z.string(),
  body: z.string(),
})

type CreateValues = z.infer<typeof createSchema>

export function SystemPromptNewPage() {
  const { t } = useTranslation('systemPrompts')
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const { locale, setLocale } = useContentLocaleField()
  const [saveError, setSaveError] = useState<string | null>(null)

  // BlockNote-Bloecke werden ausserhalb des RHF-State gepuffert, damit kein
  // Re-Render des Editors bei jedem Keystroke ausgeloest wird.
  const blocksRef = useRef<SystemPromptBlock[]>([])

  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', description: '', body: '' },
  })

  const handleBlockNoteChange = useCallback(
    (blocks: SystemPromptBlock[]) => {
      blocksRef.current = blocks
      // RHF-body-Feld mitfuehren, damit isDirty korrekt ist.
      form.setValue('body', JSON.stringify(blocks), { shouldDirty: true })
    },
    [form],
  )

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      // body ist JSON-String; falls noch nie onChange gefeuert hat → leeres Array.
      const bodyJson =
        values.body !== '' ? values.body : JSON.stringify(blocksRef.current)
      const created = await api.createSystemPromptTemplate({
        name: values.name,
        content: {
          description: values.description,
          // Track B: content traegt nur description+body. body darf nicht leer
          // sein (Pydantic min_length=1) — ein leeres BlockNote-Dok
          // serialisiert zu "[]", was OK ist.
          body: bodyJson !== '' ? bodyJson : '[]',
        },
        locale,
      })
      notify.success(t('page.new.toast.created'))
      navigate(wsPath(`/system-prompts/${created.id}`))
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : t('page.new.error.unknown'))
    }
  })

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/system-prompts')}>
            <ArrowLeft className="h-4 w-4" />
            {t('nav.backToList')}
          </Link>
        </Button>
        <PageHeader
          title={t('page.new.title')}
          description={t('page.new.description')}
        />
        <LanguageSelect value={locale} onChange={setLocale} idBase="system-prompt-lang" />
        <div className="flex flex-col gap-6">
          <Card>
            <CardContent className="pt-6">
              <Form {...form}>
                <form onSubmit={onSubmit} className="flex flex-col gap-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('common:fields.name')}</FormLabel>
                        <FormControl>
                          <Input required placeholder={t('form.identity.name.placeholder')} {...field} />
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
                        <FormLabel>{t('common:fields.description')}</FormLabel>
                        <FormControl>
                          <Input
                            placeholder={t('form.identity.description.placeholder')}
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="body"
                    render={() => (
                      <FormItem>
                        <div className="flex items-center justify-between">
                          <FormLabel>{t('form.promptBody.label')}</FormLabel>
                          <PlaceholderHelp />
                        </div>
                        <SystemPromptEditor onChange={handleBlockNoteChange} />
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
                      {t('page.new.submit')}
                    </Button>
                  </div>
                </form>
              </Form>
            </CardContent>
          </Card>
        </div>
      </Stack>
    </Container>
  )
}
