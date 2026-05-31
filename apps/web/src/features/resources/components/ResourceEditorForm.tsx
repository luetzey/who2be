import { type FormEvent, type ReactNode } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import type { ResourceBlock } from '@/api/types'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'

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
}

export function ResourceEditorForm({
  form,
  formKey,
  initialBodyBlocks,
  onSubmit,
  actions,
}: ResourceEditorFormProps) {
  const isViewer = useCurrentWorkspaceRole() === 'viewer'

  return (
    <Card>
      <CardContent className="pt-6">
        <Form {...form}>
          <form
            className="flex flex-col gap-6"
            onSubmit={onSubmit ?? ((event) => event.preventDefault())}
          >
            <FormSection
              title="Identität"
              description="Wie die Resource heißt und worum es geht."
              help={
                <p>
                  Beispiel: <em>„Datenschutz-FAQ"</em> — strukturierter
                  Wissensblock, der von Playbooks per Block-Ref eingebunden wird.
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
                      <Input
                        required
                        placeholder="z. B. Datenschutz-FAQ"
                        {...field}
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
                    <FormLabel>Beschreibung</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="z. B. Antworten auf die häufigsten Datenschutzfragen"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <FormSection
              title="Inhalt"
              description="Der eigentliche Inhalt der Resource."
              help={
                <p>
                  Einzelne Heading-Bloecke koennen per Block-Ref in Playbooks
                  eingebunden werden. Aenderungen erzeugen eine neue Version.
                </p>
              }
            >
              <FormField
                control={form.control}
                name="bodyBlocks"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Inhalt</FormLabel>
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

            {actions !== undefined ? actions : null}
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
