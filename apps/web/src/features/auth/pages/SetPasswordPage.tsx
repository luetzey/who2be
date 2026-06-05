import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import { supabase } from '@/lib/supabase'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { sanitizeNext } from '@/features/auth/lib/sanitize-next'
import { notify } from '@/lib/feedback'


type SetPasswordValues = { password: string; confirm: string }

export function SetPasswordPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  // `next` darf wieder auf die Accept-Page zeigen (inkl. `via=magic`), damit
  // der Invitation-Flow nach dem Passwort automatisch weiterlaeuft.
  // `sanitizeNext` schuetzt vor Open-Redirect — gleiche Pruefung wie LoginPage.
  const next = sanitizeNext(searchParams.get('next'))

  // Min-Laenge 8 — GoTrue-Default. Match-Check verhindert Tippfehler im
  // One-Shot-Magic-Link-Flow, wo der User noch keinen Reset-Pfad hat.
  const setPasswordSchema = z
    .object({
      password: z.string().min(8, t('validation.passwordMinLength')),
      confirm: z.string().min(1, t('validation.confirmRequired')),
    })
    .refine((values) => values.password === values.confirm, {
      message: t('validation.passwordMismatch'),
      path: ['confirm'],
    })

  const form = useForm<SetPasswordValues>({
    resolver: zodResolver(setPasswordSchema),
    defaultValues: { password: '', confirm: '' },
  })

  async function onSubmit(values: SetPasswordValues) {
    setError(null)
    const { error: updateError } = await supabase.auth.updateUser({
      password: values.password,
    })
    if (updateError) {
      setError(updateError.message)
      return
    }
    notify.success(t('setPassword.success'))
    navigate(next)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <CardTitle className="text-3xl tracking-tight">{t('setPassword.title')}</CardTitle>
          <CardDescription>
            {t('setPassword.description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('fields.newPassword')}</FormLabel>
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
              {error !== null ? <ErrorAlert message={error} /> : null}
              <Button
                type="submit"
                variant="brand"
                className="w-full"
                disabled={form.formState.isSubmitting}
              >
                {t('setPassword.submit')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </main>
  )
}
