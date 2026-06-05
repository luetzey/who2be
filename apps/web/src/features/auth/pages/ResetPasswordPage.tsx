import { zodResolver } from '@hookform/resolvers/zod'
import { MailCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { supabase } from '@/lib/supabase'

import { buildRedirectTo } from '../lib/redirect'

type ResetValues = { email: string }

// Passwort-Reset (Track K) — Schritt 1 von 2: Request. Der User gibt seine
// E-Mail ein, GoTrue verschickt eine Recovery-Mail. Der Link darin fuehrt auf
// `/onboarding/set-password` (Schritt 2: neues Passwort setzen), wo die
// Recovery-Session aus dem URL-Hash bereits aktiv ist.
//
// `next` wird gegen Open-Redirect gehaertet (`buildRedirectTo` → `sanitizeNext`)
// und nur als In-App-Pfad in die `redirectTo`-URL eingebettet — kein externer
// Origin landet je in der Recovery-Mail.
export function ResetPasswordPage() {
  const { t } = useTranslation('auth')
  const [searchParams] = useSearchParams()
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const resetSchema = z.object({
    email: z.string().email(t('validation.emailInvalid')),
  })

  const form = useForm<ResetValues>({
    resolver: zodResolver(resetSchema),
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
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('resetPassword.title')}</CardTitle>
          <CardDescription>
            {sent
              ? t('resetPassword.descriptionSent')
              : t('resetPassword.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sent ? (
            <div className="flex flex-col items-center gap-4 py-4 text-center">
              <MailCheck className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                {t('resetPassword.checkInbox')}
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link to="/login">{t('backToLogin')}</Link>
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
                      <FormLabel>{t('fields.email')}</FormLabel>
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
                  {t('resetPassword.submit')}
                </Button>
                <Button asChild variant="ghost" size="sm" className="w-full">
                  <Link to="/login">{t('backToLogin')}</Link>
                </Button>
              </form>
            </Form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
