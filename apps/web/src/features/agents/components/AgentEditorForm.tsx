import { AlertCircle } from 'lucide-react'
import { type BaseSyntheticEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { type UseFormReturn } from 'react-hook-form'

import type { Agent, Persona, SystemPromptTemplate } from '@/api/types'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { FormSection } from '@/components/layout/FormSection'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

import type { AgentEditorValues } from '../hooks/useAgentForm'
import { describeAgentMissing } from '../lib/activation'

interface AgentEditorFormProps {
  form: UseFormReturn<AgentEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
  personas: Persona[]
  templates: SystemPromptTemplate[]
  /** Gespeicherter Agent — liefert die serverseitige Aktivierbarkeit. */
  agent: Agent
  submitLabel?: string
}

export function AgentEditorForm({
  form,
  onSubmit,
  saveError,
  personas,
  templates,
  agent,
  submitLabel,
}: AgentEditorFormProps) {
  const { t } = useTranslation('agents')
  const isViewer = useCurrentWorkspaceRole() === 'viewer'

  const resolvedSubmitLabel = submitLabel ?? t('detail.submitLabel')

  // Aktivierbarkeit kommt vom Backend (Persona + Template gesetzt UND Persona
  // hat eine aktive Version). Bewusst nicht aus dem Live-Formular abgeleitet:
  // „Persona aktiv" haengt an der Versionshistorie (eine aktive Version kann
  // neben einem Draft existieren), die die Persona-Liste nicht verlaesslich
  // zeigt. Geaenderte Refs werden erst nach dem Speichern (Reload) bewertet.
  const activatable = agent.activatable
  const missing = agent.missing

  return (
    <>
      {saveError !== null ? <ErrorAlert message={saveError} /> : null}
      <Card>
        <CardContent className="pt-6">
          <Form {...form}>
            <form onSubmit={onSubmit} className="flex flex-col gap-6">
              <FormSection
                title={t('form.identity.title')}
                description={t('form.identity.description')}
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
                        <Input required {...field} />
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
                        <Textarea rows={3} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <FormSection
                title={t('form.config.title')}
                description={t('form.config.description')}
                help={
                  <p>
                    {t('form.config.help')}
                  </p>
                }
              >
                <FormField
                  control={form.control}
                  name="persona_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.persona.label')}</FormLabel>
                      <FormControl>
                        <Select disabled={isViewer} {...field}>
                          <option value="">{t('form.persona.none')}</option>
                          {personas.map((persona) => (
                            <option key={persona.id} value={persona.id}>
                              {persona.name}
                              {persona.current_status === 'active' ? '' : t('form.persona.notActive')}
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="system_prompt_template_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.template.label')}</FormLabel>
                      <FormControl>
                        <Select disabled={isViewer} {...field}>
                          <option value="">{t('form.template.none')}</option>
                          {templates.map((template) => (
                            <option key={template.id} value={template.id}>
                              {template.name} ({template.slug})
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.statusField.label')}</FormLabel>
                      <FormControl>
                        <Select disabled={isViewer} {...field}>
                          <option value="enabled" disabled={!activatable}>
                            {t('form.statusField.enabled')}
                          </option>
                          <option value="disabled">{t('form.statusField.disabled')}</option>
                        </Select>
                      </FormControl>
                      {activatable ? null : (
                        <p
                          className="flex items-start gap-2 text-sm text-muted-foreground"
                          data-testid="agent-missing-notice"
                        >
                          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                          <span>
                            {t('form.missing.notice', {
                              items: describeAgentMissing(missing).join(', '),
                            })}
                          </span>
                        </p>
                      )}
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
                  title={isViewer ? t('form.viewerReadOnly') : undefined}
                >
                  {resolvedSubmitLabel}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </>
  )
}
