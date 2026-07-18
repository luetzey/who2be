import { AlertCircle, Plug, Settings2, Wrench } from 'lucide-react'
import { type BaseSyntheticEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { type UseFormReturn } from 'react-hook-form'

import type { Agent, Persona, SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { FormSection } from '@/components/layout/FormSection'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { TagInput } from '@/components/ui/tag-input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'

import type { AgentEditorValues } from '../hooks/useAgentForm'
import { describeAgentMissing } from '../lib/activation'

// Read-Scope-Domains (Select all|assigned|none), An/Aus-Reads und Write-
// Capability-Gruppen. Reihenfolge = Anzeigereihenfolge im Formular.
const READ_SCOPE_FIELDS = [
  'playbook_read',
  'resource_read',
  'agent_read',
  'external_tool_read',
] as const
const READ_FLAG_FIELDS = ['persona_read'] as const
const WRITE_CAP_FIELDS = [
  'persona_write',
  'playbook_write',
  'resource_write',
  'agent_write',
  'system_prompt_write',
  'external_tool_write',
  'feedback_write',
  'feedback_resolve',
  'promote_retire',
] as const
const READ_SCOPES = ['all', 'assigned', 'none'] as const
const TAG_SCOPE_DOMAINS = ['persona', 'playbook', 'resource'] as const
// Per-Domain Promote/Retire (ADR-0039 transition_grants) — Checkbox-Feldnamen.
type TransitionGrantField = `tg_${(typeof TAG_SCOPE_DOMAINS)[number]}_${'promote' | 'retire'}`

// Boolean-Policy-Felder (An/Aus-Reads + Write-Capabilities + Transition-Grants).
type PolicyBoolField =
  | (typeof READ_FLAG_FIELDS)[number]
  | (typeof WRITE_CAP_FIELDS)[number]
  | TransitionGrantField

/** Eine Policy-Checkbox-Zeile im etablierten Form-Checkbox-Muster (vgl. SignupPage). */
function PolicyCheckbox({
  form,
  name,
  label,
  disabled,
}: {
  form: UseFormReturn<AgentEditorValues>
  name: PolicyBoolField
  label: string
  disabled: boolean
}) {
  const id = `agent-policy-${name}`
  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <div className="flex items-center gap-2">
          <Checkbox
            id={id}
            name={field.name}
            ref={field.ref}
            checked={Boolean(field.value)}
            onBlur={field.onBlur}
            onChange={(event) => field.onChange(event.target.checked)}
            disabled={disabled}
          />
          <Label htmlFor={id} className="text-sm font-normal">
            {label}
          </Label>
        </div>
      )}
    />
  )
}

interface AgentEditorFormProps {
  form: UseFormReturn<AgentEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
  personas: Persona[]
  templates: SystemPromptTemplate[]
  /** Gespeicherter Agent — liefert die serverseitige Aktivierbarkeit. */
  agent: Agent
  submitLabel?: string
  /**
   * Vom System verwaltet (Builder): Editor read-only wie fuer Viewer. Das
   * Backend sperrt Mutationen ohnehin (403 managed_aggregate) — die UI macht
   * es nur sichtbar und verhindert vergebliche Speicher-Versuche.
   */
  locked?: boolean
  /**
   * Inhalt des „Verbindung"-Tabs (Connector- + Token-Sektion). Liegt bewusst
   * ausserhalb des `<form>`-Elements (eigene, geschachtelte Forms) — daher als
   * Slot. Ohne diesen Prop entfaellt der Tab (Standalone-Nutzung des Editors).
   */
  connectionSlot?: ReactNode
}

export function AgentEditorForm({
  form,
  onSubmit,
  saveError,
  personas,
  templates,
  agent,
  submitLabel,
  locked = false,
  connectionSlot,
}: AgentEditorFormProps) {
  const { t } = useTranslation('agents')
  const api = useApi()
  const readOnly = useCurrentWorkspaceRole() === 'viewer' || locked
  const isViewer = readOnly

  // Tag-Vorschlaege je Domain aus der jeweils eigenen Tag-Quelle (wie Persona-/
  // Playbook-/Resource-Editor). `api` ist memoisiert → stabile Loader-Referenz.
  const tagLoaders: Record<(typeof TAG_SCOPE_DOMAINS)[number], () => Promise<string[]>> = {
    persona: api.listPersonaTags,
    playbook: api.listPlaybookTags,
    resource: api.listResourceTags,
  }

  const resolvedSubmitLabel = submitLabel ?? t('detail.submitLabel')

  const submitButton = (
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
  )

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
      <Tabs defaultValue="config">
        <TabsList aria-label={t('detail.tabsAria')}>
          <TabsTrigger value="config">
            <Settings2 aria-hidden="true" />
            {t('detail.tabs.config')}
          </TabsTrigger>
          <TabsTrigger value="tools">
            <Wrench aria-hidden="true" />
            {t('detail.tabs.tools')}
          </TabsTrigger>
          {connectionSlot !== undefined ? (
            <TabsTrigger value="connection">
              <Plug aria-hidden="true" />
              {t('detail.tabs.connection')}
            </TabsTrigger>
          ) : null}
        </TabsList>

        <Form {...form}>
          <form onSubmit={onSubmit}>
            <TabsContent value="config">
              <Card>
                <CardContent className="flex flex-col gap-6 pt-6">
                  <FormSection
                    title={t('form.identity.title')}
                    description={t('form.identity.description')}
                    help={<p>{t('form.identity.help')}</p>}
                  >
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('common:fields.name')}</FormLabel>
                      <FormControl>
                        <Input required {...field} disabled={readOnly} />
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
                        <Textarea rows={3} {...field} disabled={readOnly} />
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

                  {submitButton}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="tools">
              <Card>
                <CardContent className="flex flex-col gap-6 pt-6">
                  <FormSection
                    title={t('form.policy.title')}
                    description={t('form.policy.description')}
                    help={<p>{t('form.policy.help')}</p>}
                  >
                <fieldset className="flex flex-col gap-3" disabled={isViewer}>
                  <legend className="text-sm font-medium">{t('form.policy.reads')}</legend>
                  {READ_SCOPE_FIELDS.map((name) => {
                    // agent_read nutzt agent-spezifische Optionslabels
                    // ("Nur eigener Agent" statt "Nur zugewiesene").
                    const scopeKey = name === 'agent_read' ? 'agentScope' : 'scope'
                    return (
                      <FormField
                        key={name}
                        control={form.control}
                        name={name}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t(`form.policy.scopeField.${name}`)}</FormLabel>
                            <FormControl>
                              <Select disabled={isViewer} {...field}>
                                {READ_SCOPES.map((scope) => (
                                  <option key={scope} value={scope}>
                                    {t(`form.policy.${scopeKey}.${scope}`)}
                                  </option>
                                ))}
                              </Select>
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )
                  })}
                  {READ_FLAG_FIELDS.map((name) => (
                    <PolicyCheckbox
                      key={name}
                      form={form}
                      name={name}
                      label={t(`form.policy.flagField.${name}`)}
                      disabled={isViewer}
                    />
                  ))}
                </fieldset>

                <fieldset className="flex flex-col gap-3" disabled={isViewer}>
                  <legend className="text-sm font-medium">{t('form.policy.writes')}</legend>
                  <p className="text-sm text-muted-foreground">{t('form.policy.writesHint')}</p>
                  {WRITE_CAP_FIELDS.map((name) => (
                    <PolicyCheckbox
                      key={name}
                      form={form}
                      name={name}
                      label={t(`form.policy.capField.${name}`)}
                      disabled={isViewer}
                    />
                  ))}
                  <p className="text-sm text-muted-foreground">{t('form.policy.writeTags.hint')}</p>
                  {TAG_SCOPE_DOMAINS.map((domain) => (
                    <FormField
                      key={domain}
                      control={form.control}
                      name={`write_tags_${domain}` as const}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel id={`${field.name}-label`}>
                            {t(`form.policy.writeTags.${domain}`)}
                          </FormLabel>
                          <FormControl>
                            <TagInput
                              value={field.value}
                              onChange={field.onChange}
                              loadSuggestions={tagLoaders[domain]}
                              ariaLabelledby={`${field.name}-label`}
                              placeholder={t('form.policy.writeTags.placeholder')}
                              disabled={isViewer}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  ))}
                  <p className="text-sm text-muted-foreground">
                    {t('form.policy.transitionGrants.hint')}
                  </p>
                  {TAG_SCOPE_DOMAINS.map((domain) => (
                    <div key={domain} className="flex flex-col gap-2">
                      <span className="text-sm font-medium">
                        {t(`form.policy.transitionGrants.${domain}`)}
                      </span>
                      <PolicyCheckbox
                        form={form}
                        name={`tg_${domain}_promote`}
                        label={t('form.policy.transitionGrants.promote')}
                        disabled={isViewer}
                      />
                      <PolicyCheckbox
                        form={form}
                        name={`tg_${domain}_retire`}
                        label={t('form.policy.transitionGrants.retire')}
                        disabled={isViewer}
                      />
                    </div>
                  ))}
                  <FormField
                    control={form.control}
                    name="write_rate_limit"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('form.policy.rateLimit.label')}</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min={0}
                            placeholder={t('form.policy.rateLimit.placeholder')}
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </fieldset>
                  </FormSection>

                  {submitButton}
                </CardContent>
              </Card>
            </TabsContent>
          </form>
        </Form>

        {connectionSlot !== undefined ? (
          <TabsContent value="connection">{connectionSlot}</TabsContent>
        ) : null}
      </Tabs>
    </>
  )
}
