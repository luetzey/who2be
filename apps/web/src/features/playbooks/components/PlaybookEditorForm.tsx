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

import type { PlaybookEditorValues } from '../hooks/usePlaybookForm'

interface PlaybookEditorFormProps {
  form: UseFormReturn<PlaybookEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function PlaybookEditorForm({ form, onSubmit, saveError }: PlaybookEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Save bleibt gesperrt.
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
                description="Wie das Playbook heißt, welcher Typ es ist und worum es geht."
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
                  name="type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Typ</FormLabel>
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
                        <Input required {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <FormSection
                title="Inhalt"
                description="Das ausführliche Playbook und seine Auslöser."
                footer="Änderungen erzeugen eine neue Version. Alte Versionen bleiben erhalten."
              >
                <FormField
                  control={form.control}
                  name="body"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Inhalt</FormLabel>
                      <FormControl>
                        <Textarea required rows={8} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="tags"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tags (kommagetrennt)</FormLabel>
                      <FormControl>
                        <Input {...field} />
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
                      <FormLabel>Trigger</FormLabel>
                      <FormControl>
                        <Input {...field} />
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
    </>
  )
}
