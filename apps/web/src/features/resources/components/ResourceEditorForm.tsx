import { type FormEvent, type ReactNode } from 'react'
import { type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { TagInput } from '@/components/ui/tag-input'

import { ResourceEditor } from './ResourceEditor'
import type { ResourceEditorValues } from '../hooks/useResourceForm'

interface ResourceEditorFormProps {
  form: UseFormReturn<ResourceEditorValues>
  // Render-Identitaet fuer die BlockNote-Insel. Wechselt der Key, wird der
  // ProseMirror-State remountet — Pattern identisch zu Persona/Playbook.
  formKey: string
  // Initial-Snapshot der Body-Bloecke. `field.value` kann NICHT genutzt
  // werden, weil form.reset erst nach Mount laeuft.
  initialBodyBlocks: ResourceBlock[]
  /**
   * Optionaler onSubmit-Handler. Fehlt er, wird das Standard-preventDefault
   * genutzt (Auto-Save-Modus auf der Detail-Page).
   */
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void
  /**
   * Optionaler Actions-Slot. Wird am Ende des <form>-Elements gerendert.
   * Typisch: Submit-Button + ErrorAlert auf der New-Page.
   */
  actions?: ReactNode
  // Vom System verwaltet: Editor read-only wie fuer Viewer.
  locked?: boolean
}

export function ResourceEditorForm({
  form,
  formKey,
  initialBodyBlocks,
  onSubmit,
  actions,
  locked = false,
}: ResourceEditorFormProps) {
  const { t } = useTranslation('resources')
  const isViewer = useCurrentWorkspaceRole() === 'viewer' || locked
  const api = useApi()

  return (
    <Card>
      <CardContent className="pt-6">
        <Form {...form}>
          <form
            className="flex flex-col gap-6"
            onSubmit={onSubmit ?? ((event) => event.preventDefault())}
          >
            <FormSection
              title={t('form.identityTitle')}
              description={t('form.identityDescription')}
              help={
                <p>
                  {t('form.identityHelp')}
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
                      <Input
                        required
                        placeholder={t('form.namePlaceholder')}
                        {...field}
                        disabled={isViewer}
                      />
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
                        placeholder={t('form.descriptionPlaceholder')}
                        {...field}
                        disabled={isViewer}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <FormSection
              title={t('form.contentTitle')}
              description={t('form.contentDescription')}
              help={
                <p>
                  {t('form.contentHelp')}
                </p>
              }
            >
              <FormField
                control={form.control}
                name="bodyBlocks"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.contentLabel')}</FormLabel>
                    <FormControl>
                      <ResourceEditor
                        key={formKey}
                        initialBlocks={initialBodyBlocks}
                        editable={!isViewer}
                        onChange={(blocks: ResourceBlock[]) => field.onChange(blocks)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <FormSection
              title={t('common:fields.tags')}
              description={t('form.tagsDescription')}
              help={
                <p>
                  {t('form.tagsHelp')}
                </p>
              }
            >
              <FormField
                control={form.control}
                name="tags"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel id={`${field.name}-label`}>{t('common:fields.tags')}</FormLabel>
                    <FormControl>
                      <TagInput
                        value={field.value}
                        onChange={field.onChange}
                        loadSuggestions={api.listResourceTags}
                        ariaLabelledby={`${field.name}-label`}
                        placeholder={t('form.tagsPlaceholder')}
                        disabled={isViewer}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            {actions !== undefined ? actions : null}
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
