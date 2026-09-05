import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { config } from '@/config'
import { supabase } from '@/lib/supabase'

import { OAuthButtons } from '../components/OAuthButtons'
import { buildRedirectTo } from '../lib/redirect'
import { sanitizeNext } from '../lib/sanitize-next'
import { ComingSoonPage } from './ComingSoonPage'

type SignupValues = { email: string; password: string; confirm: string; consent: boolean }

// Min-Laenge 8 = GoTrue-Default; Confirm-Feld verhindert Tippfehler im Passwort.
// `consent` (AGB & Datenschutz) ist Pflicht — muss true sein, sonst kein Submit.
function makeSignupSchema(t: (key: string) => string) {
  return z
    .object({
      email: z.string().email(t('validation.emailInvalid')),
      password: z.string().min(8, t('validation.passwordMinLength')),
      confirm: z.string().min(1, t('validation.confirmRequired')),
      consent: z.boolean().refine((value) => value === true, {
        message: t('validation.consentRequired'),
      }),
    })
    .refine((values) => values.password === values.confirm, {
      message: t('validation.passwordMismatch'),
      path: ['confirm'],
    })
}

// Registrierung (Track K). Zwei GoTrue-Ausgaenge:
//   - Dev (`GOTRUE_MAILER_AUTOCONFIRM=true`): `signUp` liefert sofort eine
//     Session → der User ist eingeloggt, wir navigieren auf `next`.
//   - Prod (`autoconfirm=false`): `signUp` liefert KEINE Session, GoTrue
//     verschickt eine Bestaetigungs-Mail. Wir zeigen den „Pruefe dein
//     Postfach"-Zustand; der Confirm-Link landet auf `/auth/callback`.
export function SignupPage() {
  const { t } = useTranslation('auth')
  const { session } = useSession()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [confirmationPending, setConfirmationPending] = useState(false)

  const next = sanitizeNext(searchParams.get('next'))

  const signupSchema = makeSignupSchema(t)

  const form = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: '', password: '', confirm: '', consent: false },
  })

  // Gate fuer Submit UND OAuth: erst nach Zustimmung freigeschaltet (WP-I).
  const consentGiven = form.watch('consent')

  // "Wir arbeiten noch"-Modus (Issue #429, WHO2BE_LAUNCH_MODE=coming_soon):
  // Hinweisseite statt Formular. Defense-in-Depth: GoTrue weist signUp
  // ohnehin mit 422 ab (GOTRUE_DISABLE_SIGNUP).
  if (config.launchMode === 'coming_soon') {
    return <ComingSoonPage />
  }

  // Altschalter ohne Launch-Modus (VITE_WHO2BE_SIGNUP_DISABLED, spiegelt
  // GOTRUE_DISABLE_SIGNUP) → die Seite ist nicht erreichbar, zurueck zum Login.
  if (config.signupDisabled) {
    return <Navigate to="/login" replace />
  }

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
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('signup.title')}</CardTitle>
          <CardDescription>
            {confirmationPending
              ? t('signup.descriptionPending')
              : t('signup.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {confirmationPending ? (
            <div className="flex flex-col items-center gap-4 py-4 text-center">
              <MailCheck className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                {t('signup.confirmPending')}
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link to="/login">{t('backToLogin')}</Link>
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
                        <FormLabel>{t('fields.email')}</FormLabel>
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
                        <FormLabel>{t('fields.password')}</FormLabel>
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
                        <FormLabel>{t('fields.passwordRepeat')}</FormLabel>
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
                    name="consent"
                    render={({ field, fieldState }) => (
                      <FormItem>
                        <div className="flex items-start gap-2">
                          <Checkbox
                            id="signup-consent"
                            name={field.name}
                            ref={field.ref}
                            checked={field.value}
                            onBlur={field.onBlur}
                            onChange={(event) => field.onChange(event.target.checked)}
                            aria-invalid={fieldState.error ? true : undefined}
                            className="mt-0.5"
                          />
                          <Label
                            htmlFor="signup-consent"
                            className="text-sm leading-snug font-normal text-muted-foreground"
                          >
                            {t('signup.consent.before')}{' '}
                            <Link
                              to="/legal/agb"
                              target="_blank"
                              rel="noreferrer"
                              className="font-medium text-foreground underline-offset-4 hover:underline"
                            >
                              {t('signup.consent.termsLink')}
                            </Link>{' '}
                            {t('signup.consent.middle')}{' '}
                            <Link
                              to="/legal/datenschutz"
                              target="_blank"
                              rel="noreferrer"
                              className="font-medium text-foreground underline-offset-4 hover:underline"
                            >
                              {t('signup.consent.privacyLink')}
                            </Link>
                            {t('signup.consent.after')}
                          </Label>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  {error !== null ? <ErrorAlert message={error} /> : null}
                  <Button
                    type="submit"
                    variant="brand"
                    className="w-full"
                    disabled={form.formState.isSubmitting || !consentGiven}
                  >
                    {t('signup.submit')}
                  </Button>
                </form>
              </Form>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="h-px flex-1 bg-border" />
                {t('or')}
                <span className="h-px flex-1 bg-border" />
              </div>
              {!consentGiven ? (
                <p className="text-center text-xs text-muted-foreground">
                  {t('signup.consentRequiredHint')}
                </p>
              ) : null}
              <OAuthButtons next={next} disabled={!consentGiven} />
              <p className="text-center text-sm text-muted-foreground">
                {t('signup.alreadyAccount')}{' '}
                <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
                  {t('signup.signIn')}
                </Link>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
