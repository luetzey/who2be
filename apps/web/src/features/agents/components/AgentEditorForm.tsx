import { type BaseSyntheticEvent } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import type { Persona, SystemPromptTemplate } from '@/api/types'
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

interface AgentEditorFormProps {
  form: UseFormReturn<AgentEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
  personas: Persona[]
  templates: SystemPromptTemplate[]
  submitLabel?: string
}

export function AgentEditorForm({
  form,
  onSubmit,
  saveError,
  personas,
  templates,
  submitLabel = 'Speichern',
}: AgentEditorFormProps) {
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  return (
    <>
      {saveError !== null ? <ErrorAlert message={saveError} /> : null}
      <Card>
        <CardContent className="pt-6">
          <Form {...form}>
            <form onSubmit={onSubmit} className="flex flex-col gap-6">
              <FormSection
                title="Identität"
                description="Wie der Agent heißt und wofür er gedacht ist."
                help={
                  <p>
                    Beispiel: <em>„Carla Bot — Customer-Support-Agent"</em>.
                  </p>
                }
              >
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
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
                      <FormLabel>Beschreibung</FormLabel>
                      <FormControl>
                        <Textarea rows={3} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <FormSection
                title="Konfiguration"
                description="Welche Persona und welcher Systemprompt der Agent verwendet."
                help={
                  <p>
                    Die ausgewählte Persona liefert Name, Profil, Tags und ihre
                    Playbooks. Der Systemprompt definiert den eigentlichen
                    System-Prompt mit Platzhaltern.
                  </p>
                }
              >
                <FormField
                  control={form.control}
                  name="persona_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Persona</FormLabel>
                      <FormControl>
                        <Select required disabled={isViewer} {...field}>
                          <option value="" disabled>
                            — bitte wählen —
                          </option>
                          {personas.map((persona) => (
                            <option key={persona.id} value={persona.id}>
                              {persona.name}
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
                      <FormLabel>Systemprompt</FormLabel>
                      <FormControl>
                        <Select required disabled={isViewer} {...field}>
                          <option value="" disabled>
                            — bitte wählen —
                          </option>
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
                      <FormLabel>Status</FormLabel>
                      <FormControl>
                        <Select disabled={isViewer} {...field}>
                          <option value="enabled">Aktiv</option>
                          <option value="disabled">Deaktiviert</option>
                        </Select>
                      </FormControl>
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
                  title={isViewer ? 'Viewer können Agents nur ansehen' : undefined}
                >
                  {submitLabel}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </>
  )
}
