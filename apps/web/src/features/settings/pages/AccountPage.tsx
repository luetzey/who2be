import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

        <Card>
          <CardHeader>
            <CardTitle>Daten & Datenschutz</CardTitle>
            <CardDescription>Exportiere eine Kopie all deiner Daten (DSGVO).</CardDescription>
          </CardHeader>
          <CardContent>
            <DataExportSection />
          </CardContent>
        </Card>

        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle className="text-destructive">Konto löschen</CardTitle>
          </CardHeader>
          <CardContent>
            <DeleteAccountSection email={email} />
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}

function DataExportSection() {
  const api = useApi()
  const [pending, setPending] = useState(false)

  async function onExport() {
    setPending(true)
    try {
      const bundle = await api.exportMyData()
      // Browser-Download des JSON-Bündels — kein zusätzlicher Server-Roundtrip.
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'who2be-export.json'
      anchor.click()
      URL.revokeObjectURL(url)
      notify.success('Datenexport heruntergeladen.')
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : 'Export fehlgeschlagen.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        Lädt alle Organisationen, Workspaces, Personae, Playbooks, Resources, Agenten und deren
        Versionen als JSON-Datei herunter.
      </p>
      <div>
        <Button type="button" variant="outline" size="sm" onClick={() => void onExport()} disabled={pending}>
          Daten exportieren
        </Button>
      </div>
    </div>
  )
}

function DeleteAccountSection({ email }: { email: string }) {
  const api = useApi()
  const navigate = useNavigate()
  const [confirm, setConfirm] = useState('')
  const [pending, setPending] = useState(false)
  const confirmMatches = confirm.trim().toLowerCase() === email.trim().toLowerCase()

  async function onDelete() {
    setPending(true)
    try {
      await api.deleteAccount()
      // Sofort clientseitig abmelden; der GoTrue-User wird im Hard-Purge nach
      // Ablauf der 30-Tage-Grace endgültig entfernt.
      await supabase.auth.signOut({ scope: 'global' })
      notify.success('Konto zur Löschung vorgemerkt. Du wurdest abgemeldet.')
      navigate('/login', { replace: true })
    } catch (cause) {
      setPending(false)
      notify.error(cause instanceof Error ? cause.message : 'Löschen fehlgeschlagen.')
    }
  }

  return (
    <Stack gap="sm">
      <p className="text-sm text-muted-foreground">
        Dein Konto und deine persönliche Organisation werden zur Löschung vorgemerkt und nach einer
        30-tägigen Frist endgültig entfernt. Diese Aktion ist nicht widerrufbar.
      </p>
      <Dialog
        onOpenChange={(open) => {
          if (!open) {
            setConfirm('')
          }
        }}
      >
        <DialogTrigger asChild>
          <Button variant="destructive">Konto löschen</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Konto löschen</DialogTitle>
            <DialogDescription>
              Gib zur Bestätigung deine E-Mail „{email}“ ein. Nach 30 Tagen werden alle deine Daten
              endgültig gelöscht.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm-account-email">E-Mail</Label>
            <Input
              id="confirm-account-email"
              value={confirm}
              autoComplete="off"
              onChange={(event) => setConfirm(event.target.value)}
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Abbrechen</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={!confirmMatches || pending}
              onClick={() => void onDelete()}
            >
              Konto endgültig löschen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Stack>
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
