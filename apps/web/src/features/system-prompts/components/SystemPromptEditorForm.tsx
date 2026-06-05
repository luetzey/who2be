import { type BaseSyntheticEvent, useCallback } from 'react'
import { type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { FormSection } from '@/components/layout/FormSection'
import { SystemPromptEditor } from '@/components/editor/system-prompt/SystemPromptEditor'
import type { SystemPromptBlock } from '@/components/editor/system-prompt/SystemPromptEditor'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'

import type { SystemPromptEditorValues } from '../hooks/useSystemPromptForm'

import { PlaceholderHelp } from './PlaceholderHelp'

interface SystemPromptEditorFormProps {
  form: UseFormReturn<SystemPromptEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function SystemPromptEditorForm({
  form,
  onSubmit,
  saveError,
}: SystemPromptEditorFormProps) {
  const { t } = useTranslation('systemPrompts')
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const bodyValue = form.watch('body')

  // Beim BlockNote-Editor: blocks → JSON-String in form.body setzen.
  const handleBlockNoteChange = useCallback(
    (blocks: SystemPromptBlock[]) => {
      form.setValue('body', JSON.stringify(blocks), { shouldDirty: true })
    },
    [form],
  )

  // Initial-Bloecke fuer den BlockNote-Editor aus dem gespeicherten JSON
  // (Track B: `body` ist immer stringifiziertes BlockNote-JSON).
  let initialBlocks: SystemPromptBlock[] | undefined
  if (bodyValue !== '') {
    try {
      initialBlocks = JSON.parse(bodyValue) as SystemPromptBlock[]
    } catch {
      initialBlocks = undefined
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {saveError !== null ? <ErrorAlert message={saveError} /> : null}
      <Card>
          <CardContent className="pt-6">
            <Form {...form}>
              <form onSubmit={onSubmit} className="flex flex-col gap-6">
                <FormSection
                  title={t('form.identity.title')}
                  description={t('form.identity.description.placeholder')}
                  help={
                    <p>
                      {t('form.identity.help')}
                    </p>
                  }
                >
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
                </FormSection>

                <FormSection
                  title={t('form.promptBody.title')}
                  description={t('form.promptBody.description')}
                  help={
                    <p>
                      {t('form.promptBody.help')}
                    </p>
                  }
                >
                  <FormField
                    control={form.control}
                    name="body"
                    render={() => (
                      <FormItem>
                        <div className="flex items-center justify-between">
                          <FormLabel>{t('form.promptBody.label')}</FormLabel>
                          <PlaceholderHelp />
                        </div>
                        <SystemPromptEditor
                          key={initialBlocks !== undefined ? 'loaded' : 'empty'}
                          initialBlocks={initialBlocks}
                          editable={!isViewer}
                          onChange={handleBlockNoteChange}
                        />
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </FormSection>

                <div className="flex justify-end">
                  <Button
                    type="submit"
                    variant="brand"
                    disabled={form.formState.isSubmitting || isViewer}
                    title={isViewer ? t('form.viewerTooltip') : undefined}
                  >
                    {t('form.saveVersion')}
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
    </div>
  )
}
