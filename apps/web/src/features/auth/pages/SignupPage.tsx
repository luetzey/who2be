import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { z } from 'zod'

import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { supabase } from '@/lib/supabase'

import { OAuthButtons } from '../components/OAuthButtons'
import { buildRedirectTo } from '../lib/redirect'
import { sanitizeNext } from '../lib/sanitize-next'

// Min-Laenge 8 = GoTrue-Default; Confirm-Feld verhindert Tippfehler im Passwort.
const schema = z
  .object({
    email: z.string().email('Bitte gueltige E-Mail eingeben.'),
    password: z.string().min(8, 'Mindestens 8 Zeichen.'),
    confirm: z.string().min(1, 'Bitte wiederholen.'),
  })
  .refine((values) => values.password === values.confirm, {
    message: 'Passwoerter stimmen nicht ueberein.',
    path: ['confirm'],
  })

type SignupValues = z.infer<typeof schema>

// Registrierung (Track K). Zwei GoTrue-Ausgaenge:
//   - Dev (`GOTRUE_MAILER_AUTOCONFIRM=true`): `signUp` liefert sofort eine
//     Session → der User ist eingeloggt, wir navigieren auf `next`.
//   - Prod (`autoconfirm=false`): `signUp` liefert KEINE Session, GoTrue
//     verschickt eine Bestaetigungs-Mail. Wir zeigen den „Pruefe dein
//     Postfach"-Zustand; der Confirm-Link landet auf `/auth/callback`.
export function SignupPage() {
  const { session } = useSession()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [confirmationPending, setConfirmationPending] = useState(false)

  const next = sanitizeNext(searchParams.get('next'))

  const form = useForm<SignupValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '', confirm: '' },
  })

  // Bereits eingeloggt (z. B. zurueck-navigiert) → nicht erneut registrieren.
  if (session !== null && !confirmationPending) {
    return <Navigate to={next} replace />
  }

  async function onSubmit(values: SignupValues) {
    setError(null)
    const { data, error: signUpError } = await supabase.auth.signUp({
      email: values.email,
      password: values.password,
      options: { emailRedirectTo: buildRedirectTo('/auth/callback', next) },
    })
    if (signUpError) {
      setError(signUpError.message)
      return
    }
    if (data.session !== null) {
      // Autoconfirm (Dev): direkt eingeloggt.
      navigate(next)
      return
    }
    // Confirm-Mail unterwegs (Prod).
    setConfirmationPending(true)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Who2Be
          </span>
          <CardTitle className="text-3xl tracking-tight">Registrieren</CardTitle>
          <CardDescription>
            {confirmationPending
              ? 'Bestaetige deine E-Mail-Adresse ueber den Link, den wir dir geschickt haben.'
              : 'Erstelle ein Konto, um deinen Workspace einzurichten.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {confirmationPending ? (
            <div className="flex flex-col items-center gap-4 py-4 text-center">
              <MailCheck className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                Pruefe dein Postfach und folge dem Bestaetigungs-Link, um die Anmeldung
                abzuschliessen.
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link to="/login">Zurueck zur Anmeldung</Link>
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
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
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Passwort</FormLabel>
                        <FormControl>
                          <Input
                            type="password"
                            autoComplete="new-password"
                            required
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="confirm"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Passwort wiederholen</FormLabel>
                        <FormControl>
                          <Input
                            type="password"
                            autoComplete="new-password"
                            required
                            {...field}
                          />
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
                    Konto erstellen
                  </Button>
                </form>
              </Form>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="h-px flex-1 bg-border" />
                oder
                <span className="h-px flex-1 bg-border" />
              </div>
              <OAuthButtons next={next} />
              <p className="text-center text-sm text-muted-foreground">
                Schon ein Konto?{' '}
                <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
                  Anmelden
                </Link>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
