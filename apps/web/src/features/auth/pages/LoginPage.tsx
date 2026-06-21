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

  if (session !== null) {
    return <Navigate to={next} replace />
  }

  async function onSubmit(values: LoginValues) {
    setError(null)
    setUnconfirmed(false)
    try {
      await signIn(values.email, values.password)
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
          <CardTitle className="text-3xl tracking-tight">{t('login.title')}</CardTitle>
          <CardDescription>{t('login.description')}</CardDescription>
        </CardHeader>
        <CardContent>
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
        </CardContent>
      </Card>
    </main>
  )
}
