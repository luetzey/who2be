import { type BaseSyntheticEvent } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { FormSection } from '@/components/layout/FormSection'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

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
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
      <div className="flex flex-col gap-4">
        {saveError !== null ? <ErrorAlert message={saveError} /> : null}
        <Card>
          <CardContent className="pt-6">
            <Form {...form}>
              <form onSubmit={onSubmit} className="flex flex-col gap-6">
                <FormSection
                  title="Identität"
                  description="Wie das Template heißt und wofür es genutzt wird."
                  help={
                    <p>
                      Beispiel: <em>„Customer-Support-Agent v1"</em>. Beschreibung
                      taucht in der Template-Liste und im Agent-Picker auf.
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
                          <Input required placeholder="z. B. Customer-Support-Agent" {...field} />
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
                          <Input
                            placeholder="z. B. Standard-Template für Support-Agenten"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </FormSection>

                <FormSection
                  title="Prompt-Body"
                  description="Der eigentliche System-Prompt mit Liquid-Placeholdern."
                  help={
                    <p>
                      Verwende <code>{'{{ persona.name }}'}</code>,{' '}
                      <code>{'{{ playbooks }}'}</code> usw. — eine vollständige
                      Liste findest du rechts in der Placeholder-Hilfe.
                    </p>
                  }
                >
                  <FormField
                    control={form.control}
                    name="body"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Body</FormLabel>
                        <FormControl>
                          <Textarea
                            required
                            rows={18}
                            placeholder="Du bist {{ persona.name }} — …"
                            className="font-mono text-sm"
                            disabled={isViewer}
                            {...field}
                          />
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
                    title={isViewer ? 'Viewer können Inhalte nur ansehen' : undefined}
                  >
                    Neue Version speichern
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
      <aside
        aria-label="Placeholder-Hilfe"
        className="lg:sticky lg:top-4 lg:self-start"
      >
        <PlaceholderHelp compact />
      </aside>
    </div>
  )
}
