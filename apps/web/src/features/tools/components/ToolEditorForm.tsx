import { type FormEvent, type ReactNode } from 'react'
import { type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ResourceBlock } from '@/api/types'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { TagInput } from '@/components/ui/tag-input'

import { ResourceEditor } from '@/components/editor/ResourceEditor'
import type { ToolEditorValues } from '../hooks/useToolForm'

interface ToolEditorFormProps {
  form: UseFormReturn<ToolEditorValues>
  // Render-Identitaet fuer die BlockNote-Insel. Wechselt der Key, wird der
  // ProseMirror-State remountet — Pattern identisch zu Resource/Playbook.
  formKey: string
  // Initial-Snapshot der Usage-Notes-Bloecke. `field.value` kann NICHT
  // genutzt werden, weil form.reset erst nach Mount laeuft.
  initialUsageNotesBlocks: ResourceBlock[]
  /**
   * Workspace-eindeutiger Faehigkeits-Alias (Migration 0065). Nur auf der
   * Detail-Page gesetzt — beim Anlegen existiert er noch nicht (der Server
   * leitet ihn aus dem Namen ab). Immer read-only: kein Feld in
   * `ExternalToolUpdate` (Alias ist nach dem Create unveraenderlich).
   */
  alias?: string
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

export function ToolEditorForm({
  form,
  formKey,
  initialUsageNotesBlocks,
  alias,
  onSubmit,
  actions,
  locked = false,
}: ToolEditorFormProps) {
  const { t } = useTranslation('tools')
  const isViewer = useCurrentWorkspaceRole() === 'viewer' || locked

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
              help={<p>{t('form.identityHelp')}</p>}
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
              {alias !== undefined ? (
                // Kein `FormField` — Alias ist kein Form-State-Feld (immutabel
                // nach dem Anlegen, kein Eintrag in `ExternalToolUpdate`).
                // `FormLabel`/`FormControl` brauchen den `FormField`-Context
                // (`useFormField`); hier reichen die schlichten Primitives.
                <div className="space-y-2">
                  <Label htmlFor="tool-alias">{t('form.aliasLabel')}</Label>
                  <Input id="tool-alias" value={alias} disabled readOnly className="font-mono" />
                  <p className="text-xs text-muted-foreground">{t('form.aliasHelp')}</p>
                </div>
              ) : null}
              <FormField
                control={form.control}
                name="displayName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.displayNameLabel')}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t('form.displayNamePlaceholder')}
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
                name="mcpServerName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.mcpServerNameLabel')}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t('form.mcpServerNamePlaceholder')}
                        {...field}
                        disabled={isViewer}
                      />
                    </FormControl>
                    <p className="text-xs text-muted-foreground">{t('form.mcpServerNameHelp')}</p>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="toolNames"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel id={`${field.name}-label`}>{t('form.toolNamesLabel')}</FormLabel>
                    <FormControl>
                      <TagInput
                        value={field.value}
                        onChange={field.onChange}
                        ariaLabelledby={`${field.name}-label`}
                        placeholder={t('form.toolNamesPlaceholder')}
                        disabled={isViewer}
                      />
                    </FormControl>
                    <p className="text-xs text-muted-foreground">{t('form.toolNamesHelp')}</p>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <FormSection
              title={t('form.usageNotesTitle')}
              description={t('form.usageNotesDescription')}
              help={<p>{t('form.usageNotesHelp')}</p>}
            >
              <FormField
                control={form.control}
                name="usageNotesBlocks"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.usageNotesLabel')}</FormLabel>
                    <FormControl>
                      <ResourceEditor
                        key={formKey}
                        initialBlocks={initialUsageNotesBlocks}
                        editable={!isViewer}
                        onChange={(blocks: ResourceBlock[]) => field.onChange(blocks)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="fallbackNote"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.fallbackNoteLabel')}</FormLabel>
                    <FormControl>
                      <Textarea
                        rows={3}
                        placeholder={t('form.fallbackNotePlaceholder')}
                        {...field}
                        disabled={isViewer}
                      />
                    </FormControl>
                    <p className="text-xs text-muted-foreground">{t('form.fallbackNoteHelp')}</p>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <FormSection
              title={t('common:fields.tags')}
              description={t('form.tagsDescription')}
              help={<p>{t('form.tagsHelp')}</p>}
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
