import { useForm } from 'react-hook-form'

import { FormSection } from '@/components/layout/FormSection'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

interface DemoValues {
  name: string
  description: string
  systemPrompt: string
  traits: string
}

export function FormSectionShowcase() {
  const form = useForm<DemoValues>({
    defaultValues: { name: '', description: '', systemPrompt: '', traits: '' },
  })

  return (
    <ShowcaseSection
      id="form-section"
      title="FormSection"
      description="Gruppiert Felder in Editor-Forms. Title + optionale Description + optionaler Footer. Erste Section ohne Border-Top."
    >
      <ShowcaseRow label="Zwei Sections nacheinander">
        <div className="w-full max-w-2xl">
          <Form {...form}>
            <form className="flex flex-col gap-6">
              <FormSection
                title="Identitaet"
                description="Wie die Persona heisst und kurz beschrieben wird."
              >
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl>
                        <Input {...field} />
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
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <FormSection
                title="Verhalten"
                description="System-Prompt und Eigenschaften — bestimmen, wie der Agent antwortet."
                footer="Aenderungen erzeugen eine neue Version. Alte Versionen bleiben erhalten."
              >
                <FormField
                  control={form.control}
                  name="systemPrompt"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>System-Prompt</FormLabel>
                      <FormControl>
                        <Textarea rows={4} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="traits"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Eigenschaften (kommagetrennt)</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <div className="flex justify-end">
                <Button type="button" variant="brand">
                  Neue Version speichern
                </Button>
              </div>
            </form>
          </Form>
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
