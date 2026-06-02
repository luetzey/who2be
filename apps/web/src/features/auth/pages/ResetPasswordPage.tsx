import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router-dom'
import { z } from 'zod'

import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { supabase } from '@/lib/supabase'

import { buildRedirectTo } from '../lib/redirect'

const schema = z.object({
  email: z.string().email('Bitte gueltige E-Mail eingeben.'),
})

type ResetValues = z.infer<typeof schema>

// Passwort-Reset (Track K) — Schritt 1 von 2: Request. Der User gibt seine
// E-Mail ein, GoTrue verschickt eine Recovery-Mail. Der Link darin fuehrt auf
// `/onboarding/set-password` (Schritt 2: neues Passwort setzen), wo die
// Recovery-Session aus dem URL-Hash bereits aktiv ist.
//
// `next` wird gegen Open-Redirect gehaertet (`buildRedirectTo` → `sanitizeNext`)
// und nur als In-App-Pfad in die `redirectTo`-URL eingebettet — kein externer
// Origin landet je in der Recovery-Mail.
export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const form = useForm<ResetValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '' },
  })

  async function onSubmit(values: ResetValues) {
    setError(null)
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(values.email, {
      redirectTo: buildRedirectTo('/onboarding/set-password', searchParams.get('next')),
    })
    if (resetError) {
      setError(resetError.message)
      return
    }
    setSent(true)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Who2Be
          </span>
          <CardTitle className="text-3xl tracking-tight">Passwort zuruecksetzen</CardTitle>
          <CardDescription>
            {sent
              ? 'Wenn ein Konto zu dieser E-Mail existiert, ist eine Mail mit Reset-Link unterwegs.'
              : 'Wir senden dir einen Link, mit dem du ein neues Passwort setzen kannst.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sent ? (
            <div className="flex flex-col items-center gap-4 py-4 text-center">
              <MailCheck className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                Pruefe dein Postfach und folge dem Link in der E-Mail.
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link to="/login">Zurueck zur Anmeldung</Link>
              </Button>
            </div>
          ) : (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>E-Mail</FormLabel>
                      <FormControl>
                        <Input type="email" autoComplete="email" required {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {error !== null ? <ErrorAlert message={error} /> : null}
                <Button
                  type="submit"
                  variant="brand"
                  className="w-full"
                  disabled={form.formState.isSubmitting}
                >
                  Reset-Link senden
                </Button>
                <Button asChild variant="ghost" size="sm" className="w-full">
                  <Link to="/login">Zurueck zur Anmeldung</Link>
                </Button>
              </form>
            </Form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
