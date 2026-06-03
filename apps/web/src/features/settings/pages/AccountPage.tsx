import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { supabase } from '@/lib/supabase'
import { notify } from '@/lib/feedback'

// Konto-Self-Service (Track K). Mutationen laufen ueber GoTrue
// (`supabase.auth.updateUser`/`signOut`); die Anzeige speist sich aus der
// Supabase-Session. E-Mail-Wechsel loest eine erneute Bestaetigung aus —
// die alte Adresse bleibt bis zur Bestaetigung aktiv.
export function AccountPage() {
  const { session, me } = useSession()
  const email = session?.user?.email ?? '—'
  const userId = me?.user_id ?? session?.user?.id ?? '—'
  const hasPassword = me?.has_password ?? false
  const initialName =
    (session?.user?.user_metadata?.display_name as string | undefined) ?? ''

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Konto"
          description="Dein persönliches Profil, Sicherheit und Anzeige-Präferenzen."
        />

        <Card>
          <CardHeader>
            <CardTitle>Profil</CardTitle>
            <CardDescription>Anzeigename und Anmelde-E-Mail.</CardDescription>
          </CardHeader>
          <CardContent>
            <Stack gap="lg">
              <ProfileForm initialName={initialName} />
              <ChangeEmailForm currentEmail={email} />
              <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">User-ID</dt>
                <dd className="font-mono text-xs break-all text-muted-foreground">{userId}</dd>
              </dl>
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sicherheit</CardTitle>
            <CardDescription>Passwort und aktive Sitzungen.</CardDescription>
          </CardHeader>
          <CardContent>
            <Stack gap="lg">
              <ChangePasswordForm hasPassword={hasPassword} />
              <SignOutEverywhere />
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Präferenzen</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-4">
              <div className="text-sm">
                <div className="font-medium">Darstellung</div>
                <p className="text-muted-foreground">Hell, Dunkel oder Systemvorgabe.</p>
              </div>
              <ThemeToggle />
            </div>
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}

const nameSchema = z.object({
  display_name: z.string().trim().min(1, 'Bitte einen Namen eingeben.').max(120, 'Maximal 120 Zeichen.'),
})

function ProfileForm({ initialName }: { initialName: string }) {
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof nameSchema>>({
    resolver: zodResolver(nameSchema),
    defaultValues: { display_name: initialName },
  })

  async function onSubmit(values: z.infer<typeof nameSchema>) {
    setError(null)
    const { error: updateError } = await supabase.auth.updateUser({
      data: { display_name: values.display_name },
    })
    if (updateError) {
      setError(updateError.message)
      return
    }
    notify.success('Anzeigename gespeichert.')
    form.reset({ display_name: values.display_name })
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-3">
        <FormField
          control={form.control}
          name="display_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Anzeigename</FormLabel>
              <FormControl>
                <Input autoComplete="name" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {error !== null ? <ErrorAlert message={error} /> : null}
        <div>
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={form.formState.isSubmitting || !form.formState.isDirty}
          >
            Speichern
          </Button>
        </div>
      </form>
    </Form>
  )
}

const emailSchema = z.object({
  email: z.string().email('Bitte gueltige E-Mail eingeben.'),
})

function ChangeEmailForm({ currentEmail }: { currentEmail: string }) {
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof emailSchema>>({
    resolver: zodResolver(emailSchema),
    defaultValues: { email: '' },
  })

  async function onSubmit(values: z.infer<typeof emailSchema>) {
    setError(null)
    if (values.email === currentEmail) {
      setError('Das ist bereits deine aktuelle E-Mail-Adresse.')
      return
    }
    // GoTrue schickt eine Bestaetigungs-Mail an die NEUE Adresse; die alte
    // bleibt aktiv, bis der Link bestaetigt ist (Re-Confirm).
    const { error: updateError } = await supabase.auth.updateUser({ email: values.email })
    if (updateError) {
      setError(updateError.message)
      return
    }
    notify.success('Bestaetigungs-Mail an die neue Adresse gesendet.')
    form.reset({ email: '' })
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-3">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>E-Mail aendern</FormLabel>
              <FormControl>
                <Input type="email" autoComplete="email" placeholder={currentEmail} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <p className="text-xs text-muted-foreground">
          Aktuell: <span className="font-medium text-foreground">{currentEmail}</span>. Eine neue
          Adresse muss ueber einen Bestaetigungs-Link aktiviert werden.
        </p>
        {error !== null ? <ErrorAlert message={error} /> : null}
        <div>
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={form.formState.isSubmitting}
          >
            E-Mail aendern
          </Button>
        </div>
      </form>
    </Form>
  )
}

const passwordSchema = z
  .object({
    password: z.string().min(8, 'Mindestens 8 Zeichen.'),
    confirm: z.string().min(1, 'Bitte wiederholen.'),
  })
  .refine((values) => values.password === values.confirm, {
    message: 'Passwoerter stimmen nicht ueberein.',
    path: ['confirm'],
  })

function ChangePasswordForm({ hasPassword }: { hasPassword: boolean }) {
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { password: '', confirm: '' },
  })

  async function onSubmit(values: z.infer<typeof passwordSchema>) {
    setError(null)
    const { error: updateError } = await supabase.auth.updateUser({ password: values.password })
    if (updateError) {
      setError(updateError.message)
      return
    }
    notify.success(hasPassword ? 'Passwort geaendert.' : 'Passwort gesetzt.')
    form.reset({ password: '', confirm: '' })
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-3">
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{hasPassword ? 'Neues Passwort' : 'Passwort setzen'}</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="new-password" {...field} />
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
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {!hasPassword ? (
          <p className="text-xs text-muted-foreground">
            Du bist per Magic-Link oder Social-Login angemeldet. Mit einem Passwort kannst du dich
            auch direkt anmelden.
          </p>
        ) : null}
        {error !== null ? <ErrorAlert message={error} /> : null}
        <div>
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={form.formState.isSubmitting}
          >
            {hasPassword ? 'Passwort aendern' : 'Passwort setzen'}
          </Button>
        </div>
      </form>
    </Form>
  )
}

function SignOutEverywhere() {
  const navigate = useNavigate()
  const [pending, setPending] = useState(false)

  async function signOutEverywhere() {
    setPending(true)
    // `scope: 'global'` widerruft alle Refresh-Tokens des Users ueber alle
    // Geraete/Tabs hinweg — nicht nur die lokale Sitzung.
    const { error } = await supabase.auth.signOut({ scope: 'global' })
    if (error) {
      setPending(false)
      notify.error(error.message)
      return
    }
    notify.success('Auf allen Geraeten abgemeldet.')
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm">
        <div className="font-medium">Überall abmelden</div>
        <p className="text-muted-foreground">
          Beendet alle aktiven Sitzungen auf allen Geräten.
        </p>
      </div>
      <div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void signOutEverywhere()}
          disabled={pending}
        >
          Überall abmelden
        </Button>
      </div>
    </div>
  )
}
