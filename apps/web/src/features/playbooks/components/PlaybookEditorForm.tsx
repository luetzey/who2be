import { type FormEvent, type ReactNode } from 'react'
import { type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { PlaybookType, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { TagInput } from '@/components/ui/tag-input'

import { PLAYBOOK_TYPES, type PlaybookEditorValues } from '../hooks/usePlaybookForm'

import { PlaybookBodyEditor, type PlaybookBodyBlock } from './PlaybookBodyEditor'

interface PlaybookEditorFormProps {
  form: UseFormReturn<PlaybookEditorValues>
  // Render-Identitaet fuer die BlockNote-Insel. Wechselt der Key, wird der
  // ProseMirror-State remountet — sonst bleibt der Editor auf dem alten
  // `initialContent` haengen (useCreateBlockNote initialisiert nur einmal).
  formKey: string
  // Initial-Snapshot der Body-Bloecke aus dem playbook-Prop (siehe
  // usePlaybookForm) — `field.value` wuerde den alten Form-State zeigen,
  // weil form.reset erst im Effect nach dem Mount laeuft.
  initialBodyBlocks: ResourceBlock[]
  // Detail-Page nutzt Auto-Save, dort bleibt der Default (preventDefault).
  // Neu-Page reicht einen handleSubmit-Callback durch.
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void
  // Optionaler Slot fuer Submit-/Cancel-Buttons (nur Neu-Page).
  actions?: ReactNode
}

interface TypeOption {
  value: PlaybookType
  label: string
  hint: string
}

// Labels for playbook types — same across all languages (they are technical terms).
const TYPE_LABELS: Record<PlaybookType, string> = {
  prompt: 'Prompt',
  instructions: 'Instructions',
  snippet: 'Snippet',
  workflow: 'Workflow',
  checklist: 'Checklist',
  faq: 'FAQ',
}

export function PlaybookEditorForm({
  form,
  formKey,
  initialBodyBlocks,
  onSubmit,
  actions,
}: PlaybookEditorFormProps) {
  const { t } = useTranslation('playbooks')
  // Viewer dürfen nur lesen (ADR-0023) — Auto-Save deaktiviert sich auf
  // Detail-Page-Ebene.
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const api = useApi()
  const currentType = form.watch('type')

  // TYPE_OPTIONS must be inside the component so `t()` runs within render context.
  const typeOptions: readonly TypeOption[] = PLAYBOOK_TYPES.map((value) => ({
    value,
    label: TYPE_LABELS[value],
    hint: t(`typeHints.${value}`),
  }))

  const currentHint =
    typeOptions.find((option) => option.value === currentType)?.hint ?? null

  // BlockNote-onChange: das aktuelle Dokument (inkl. Pills) in `bodyBlocks`
  // schreiben. `toInput` serialisiert es via JSON.stringify.
  const handleBlockNoteChange = (blocks: PlaybookBodyBlock[]) => {
    form.setValue('bodyBlocks', blocks as unknown as ResourceBlock[], {
      shouldDirty: true,
    })
  }

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
                  <div className="space-y-2">
                    <p>
                      {t('form.identityHelpExample')}<em>{t('form.identityHelpExampleText')}</em>{t('form.identityHelpExampleSuffix')}
                    </p>
                    <p className="text-xs font-medium text-foreground">{t('form.identityHelpTypesHeading')}</p>
                    <ul className="list-disc space-y-1 pl-4 text-xs">
                      {typeOptions.map((option) => (
                        <li key={option.value}>
                          <strong>{option.label}:</strong> {option.hint}
                        </li>
                      ))}
                    </ul>
                  </div>
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
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.typeLabel')}</FormLabel>
                      <FormControl>
                        <Select required {...field}>
                          {PLAYBOOK_TYPES.map((option) => {
                            const meta = typeOptions.find((entry) => entry.value === option)
                            return (
                              <option key={option} value={option}>
                                {meta?.label ?? option}
                              </option>
                            )
                          })}
                        </Select>
                      </FormControl>
                      {currentHint !== null ? (
                        <p className="text-xs text-muted-foreground">{currentHint}</p>
                      ) : null}
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
                          required
                          placeholder={t('form.descriptionPlaceholder')}
                          {...field}
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
                  <p>{t('form.contentHelp')}</p>
                }
              >
                <FormField
                  control={form.control}
                  name="bodyBlocks"
                  render={() => (
                    <FormItem>
                      <FormLabel>{t('form.bodyLabel')}</FormLabel>
                      <FormControl>
                        <PlaybookBodyEditor
                          key={`${formKey}-blocknote`}
                          initialBlocks={initialBodyBlocks as PlaybookBodyBlock[]}
                          editable={!isViewer}
                          onChange={handleBlockNoteChange}
                        />
                      </FormControl>
                      <p className="text-xs text-muted-foreground">
                        {t('form.bodyHint')}
                      </p>
                      <FormMessage />
                    </FormItem>
                  )}
                />
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
                          loadSuggestions={api.listPlaybookTags}
                          ariaLabelledby={`${field.name}-label`}
                          placeholder={t('form.tagsPlaceholder')}
                          disabled={isViewer}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="triggers"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel id={`${field.name}-label`}>{t('form.triggersLabel')}</FormLabel>
                      <FormControl>
                        <TagInput
                          value={field.value}
                          onChange={field.onChange}
                          ariaLabelledby={`${field.name}-label`}
                          placeholder={t('form.triggersPlaceholder')}
                          disabled={isViewer}
                        />
                      </FormControl>
                      <p className="text-xs text-muted-foreground">
                        {t('form.triggersHint')}
                      </p>
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
