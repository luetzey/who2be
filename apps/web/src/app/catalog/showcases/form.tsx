import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

const schema = z.object({
  name: z.string().min(2, 'Mindestens 2 Zeichen.'),
  bio: z.string().max(280, 'Maximal 280 Zeichen.'),
})

type FormValues = z.infer<typeof schema>

export function FormShowcase() {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', bio: '' },
    mode: 'onTouched',
  })

  return (
    <ShowcaseSection
      id="form"
      title="Form"
      description="react-hook-form + zod + shadcn Form-Wrapper. FormField verknuepft Label, Control, Description und Error-Message via aria-describedby/aria-invalid."
    >
      <Form {...form}>
        <form
          className="flex w-full max-w-md flex-col gap-4"
          onSubmit={form.handleSubmit(() => {
            /* showcase only */
          })}
          noValidate
        >
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl>
                  <Input placeholder="z.B. Backend Reviewer" {...field} />
                </FormControl>
                <FormDescription>Pflichtfeld, Minimum 2 Zeichen.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="bio"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Kurzbeschreibung</FormLabel>
                <FormControl>
                  <Textarea rows={3} placeholder="Optional…" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <ShowcaseRow>
            <Button type="submit">Speichern</Button>
            <Button type="button" variant="ghost" onClick={() => form.reset()}>
              Zuruecksetzen
            </Button>
          </ShowcaseRow>
        </form>
      </Form>
    </ShowcaseSection>
  )
}
