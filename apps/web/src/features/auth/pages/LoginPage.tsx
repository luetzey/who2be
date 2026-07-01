import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { config } from '@/config'
import { useSession } from '@/auth/session-context'
import { supabase } from '@/lib/supabase'
import { notify } from '@/lib/feedback'

import { OAuthButtons } from '../components/OAuthButtons'
import { buildRedirectTo } from '../lib/redirect'
import { sanitizeNext } from '../lib/sanitize-next'

type LoginValues = { email: string; password: string }
type MfaValues = { code: string }

// Step-up-Challenge (WP-F/S1): Hat der Account einen verifizierten TOTP-Faktor,
// liefert der Passwort-Login nur eine aal1-Session. Diese Challenge hebt sie auf
// aal2 — ohne sie bleiben Admin-Aktionen serverseitig geblockt. Analog zum
// Enrollment in `settings/components/MfaSection.tsx` ueber `supabase.auth.mfa`.
async function completeMfaChallenge(code: string): Promise<void> {
  const { data: factors, error: listError } = await supabase.auth.mfa.listFactors()
  if (listError || factors === null) {
    throw new Error(listError?.message ?? 'MFA-Faktoren konnten nicht geladen werden.')
  }
  // `totp` enthaelt nur verifizierte Faktoren — der erste genuegt fuer die
  // Step-up-Challenge (Reihenfolge/Auswahl irrelevant, alle heben auf aal2).
  if (factors.totp.length === 0) {
    throw new Error('Kein verifizierter TOTP-Faktor gefunden.')
  }
  const factorId = factors.totp[0].id
  const { data: challenge, error: challengeError } = await supabase.auth.mfa.challenge({ factorId })
  if (challengeError || challenge === null) {
    throw new Error(challengeError?.message ?? 'MFA-Challenge konnte nicht gestartet werden.')
  }
  const { error: verifyError } = await supabase.auth.mfa.verify({
    factorId,
    challengeId: challenge.id,
    code,
  })
  if (verifyError) {
    throw new Error(verifyError.message)
  }
}

// GoTrue meldet einen noch nicht bestaetigten Account mit diesem Code; wir
// fuehren den User dann gezielt zum erneuten Versand der Confirm-Mail.
function isUnconfirmedEmail(cause: unknown): boolean {
  return (
    cause instanceof Error &&
    /email not confirmed|not confirmed/i.test(cause.message)
  )
}

export function LoginPage() {
  const { t } = useTranslation('auth')
  const { session, signIn } = useSession()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  // Unbestaetigter Login: blendet den „Bestaetigungs-Mail erneut senden"-CTA ein.
  const [unconfirmed, setUnconfirmed] = useState(false)
  // Zweite Login-Stufe: Passwort war korrekt, aber der Account braucht eine
  // TOTP-Challenge (Step-up auf aal2), bevor die Session in die App darf.
  const [mfaRequired, setMfaRequired] = useState(false)

  // `next` bringt den User nach dem Login dorthin zurück, wo ihn ein
  // Auth-Gate abgefangen hat (z. B. /invitations/:token/accept). Nur relative
  // In-App-Pfade zulassen — Browser interpretieren `//evil.com` und
  // `https://evil.com` als externe URL → Open-Redirect-Risiko.
  const next = sanitizeNext(searchParams.get('next'))

  const loginSchema = z.object({
    email: z.string().email(t('validation.emailInvalid')),
    password: z.string().min(1, t('validation.passwordRequired')),
  })

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const mfaSchema = z.object({
    code: z
      .string()
      .trim()
      .regex(/^\d{6}$/, t('login.mfa.codeInvalid')),
  })
  const mfaForm = useForm<MfaValues>({
    resolver: zodResolver(mfaSchema),
    defaultValues: { code: '' },
  })

  if (session !== null) {
    return <Navigate to={next} replace />
  }

  async function onSubmit(values: LoginValues) {
    setError(null)
    setUnconfirmed(false)
    try {
      const { mfaRequired: needsMfa } = await signIn(values.email, values.password)
      if (needsMfa) {
        // Session noch nicht committed — erst die Challenge, dann navigiert der
        // reaktive `session !== null`-Guard von selbst.
        setMfaRequired(true)
        return
      }
      navigate(next)
    } catch (cause) {
      if (isUnconfirmedEmail(cause)) {
        setUnconfirmed(true)
        setError(t('login.unconfirmedEmail'))
        return
      }
      setError(cause instanceof Error ? cause.message : t('login.loginFailed'))
    }
  }

  async function onVerifyMfa(values: MfaValues) {
    setError(null)
    try {
      await completeMfaChallenge(values.code)
      // `verify` hebt die Session auf aal2; `SessionProvider.apply()` committet
      // sie ueber onAuthStateChange, woraufhin der Guard oben nach `next`
      // navigiert. Kein manuelles navigate() → keine Race gegen den Commit.
    } catch {
      // Haeufigster Fall ist ein falscher Code; interne Invarianten (kein
      // Faktor, Challenge-Fehler) fallen auf dieselbe lokalisierte Meldung —
      // die rohen GoTrue-/Guard-Messages werden bewusst nicht durchgereicht.
      mfaForm.reset({ code: '' })
      setError(t('login.mfa.failed'))
    }
  }

  async function resendConfirmation() {
    const email = form.getValues('email')
    const { error: resendError } = await supabase.auth.resend({
      type: 'signup',
      email,
      options: { emailRedirectTo: buildRedirectTo('/auth/callback', next) },
    })
    if (resendError) {
      notify.error(resendError.message)
      return
    }
    notify.success(t('login.confirmationResent'))
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">
            {mfaRequired ? t('login.mfa.title') : t('login.title')}
          </CardTitle>
          <CardDescription>
            {mfaRequired ? t('login.mfa.description') : t('login.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {mfaRequired ? (
            <Form {...mfaForm}>
              <form onSubmit={mfaForm.handleSubmit(onVerifyMfa)} className="flex flex-col gap-4">
                <FormField
                  control={mfaForm.control}
                  name="code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('login.mfa.codeLabel')}</FormLabel>
                      <FormControl>
                        <Input
                          inputMode="numeric"
                          autoComplete="one-time-code"
                          placeholder={t('login.mfa.codePlaceholder')}
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
                  disabled={mfaForm.formState.isSubmitting}
                >
                  {t('login.mfa.submit')}
                </Button>
              </form>
            </Form>
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
                      <div className="flex items-center justify-between">
                        <FormLabel>{t('fields.password')}</FormLabel>
                        <Link
                          to={
                            next === '/'
                              ? '/reset-password'
                              : `/reset-password?next=${encodeURIComponent(next)}`
                          }
                          className="text-xs text-muted-foreground underline-offset-4 hover:underline"
                        >
                          {t('login.forgotPassword')}
                        </Link>
                      </div>
                      <FormControl>
                        <Input
                          type="password"
                          autoComplete="current-password"
                          required
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {error !== null ? <ErrorAlert message={error} /> : null}
                {unconfirmed ? (
                  <Button type="button" variant="outline" size="sm" onClick={() => void resendConfirmation()}>
                    {t('login.resendConfirmation')}
                  </Button>
                ) : null}
                <Button
                  type="submit"
                  variant="brand"
                  className="w-full"
                  disabled={form.formState.isSubmitting}
                >
                  {t('login.submit')}
                </Button>
              </form>
            </Form>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-border" />
              {t('or')}
              <span className="h-px flex-1 bg-border" />
            </div>
            <OAuthButtons next={next} />
            {/* Self-Service-Registrierung nur zeigen, wenn nicht deaktiviert
                (VITE_WHO2BE_SIGNUP_DISABLED, spiegelt GOTRUE_DISABLE_SIGNUP). */}
            {!config.signupDisabled && (
              <p className="text-center text-sm text-muted-foreground">
                {t('login.noAccount')}{' '}
                <Link
                  to={next === '/' ? '/signup' : `/signup?next=${encodeURIComponent(next)}`}
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                >
                  {t('login.register')}
                </Link>
              </p>
            )}
          </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
