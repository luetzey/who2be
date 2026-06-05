import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
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
import { Select } from '@/components/ui/select'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { LOCALE_LABELS } from '@/i18n'
import type { Locale } from '@/i18n'
import { useLocale } from '@/i18n/useLocale'
import { supabase } from '@/lib/supabase'
import { notify } from '@/lib/feedback'

import { MfaSection } from '../components/MfaSection'


// Konto-Self-Service (Track K). Mutationen laufen ueber GoTrue
// (`supabase.auth.updateUser`/`signOut`); die Anzeige speist sich aus der
// Supabase-Session. E-Mail-Wechsel loest eine erneute Bestaetigung aus —
// die alte Adresse bleibt bis zur Bestaetigung aktiv.
export function AccountPage() {
  const { t } = useTranslation('settings')
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
          title={t('account.title')}
          description={t('account.description')}
        />

        <Card>
          <CardHeader>
            <CardTitle>{t('account.profile.title')}</CardTitle>
            <CardDescription>{t('account.profile.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <Stack gap="lg">
              <ProfileForm initialName={initialName} />
              <ChangeEmailForm currentEmail={email} />
              <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">{t('account.profile.userId')}</dt>
                <dd className="font-mono text-xs break-all text-muted-foreground">{userId}</dd>
              </dl>
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('account.security.title')}</CardTitle>
            <CardDescription>{t('account.security.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <Stack gap="lg">
              <ChangePasswordForm hasPassword={hasPassword} />
              <MfaSection />
              <SignOutEverywhere />
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('account.preferences.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Stack gap="md">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm">
                  <div className="font-medium">{t('account.preferences.theme.title')}</div>
                  <p className="text-muted-foreground">{t('account.preferences.theme.description')}</p>
                </div>
                <ThemeToggle />
              </div>
              <LanguageRow />
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('account.dataPrivacy.title')}</CardTitle>
            <CardDescription>{t('account.dataPrivacy.description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <DataExportSection />
          </CardContent>
        </Card>

        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle className="text-destructive">{t('account.deleteAccount.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <DeleteAccountSection email={email} />
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}

function LanguageRow() {
  const { t } = useTranslation('settings')
  const { locale, locales, setLocale } = useLocale()

  return (
    <div className="flex items-center justify-between gap-4">
      <div className="text-sm">
        <Label htmlFor="language-select" className="font-medium">
          {t('language.label')}
        </Label>
        <p className="text-muted-foreground">{t('language.description')}</p>
      </div>
      <Select
        id="language-select"
        value={locale}
        onChange={(event) => setLocale(event.target.value as Locale)}
        className="w-auto"
        aria-label={t('language.label')}
      >
        {locales.map((loc) => (
          <option key={loc} value={loc}>
            {LOCALE_LABELS[loc]}
          </option>
        ))}
      </Select>
    </div>
  )
}

function DataExportSection() {
  const { t } = useTranslation('settings')
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
      notify.success(t('account.dataPrivacy.exportSuccess'))
    } catch (cause) {
      notify.error(cause instanceof Error ? cause.message : t('account.dataPrivacy.exportError'))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        {t('account.dataPrivacy.exportHint')}
      </p>
      <div>
        <Button type="button" variant="outline" size="sm" onClick={() => void onExport()} disabled={pending}>
          {t('account.dataPrivacy.exportButton')}
        </Button>
      </div>
    </div>
  )
}

function DeleteAccountSection({ email }: { email: string }) {
  const { t } = useTranslation('settings')
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
      notify.success(t('account.deleteAccount.successToast'))
      navigate('/login', { replace: true })
    } catch (cause) {
      setPending(false)
      notify.error(cause instanceof Error ? cause.message : t('account.deleteAccount.errorFallback'))
    }
  }

  return (
    <Stack gap="sm">
      <p className="text-sm text-muted-foreground">
        {t('account.deleteAccount.description')}
      </p>
      <Dialog
        onOpenChange={(open) => {
          if (!open) {
            setConfirm('')
          }
        }}
      >
        <DialogTrigger asChild>
          <Button variant="destructive">{t('account.deleteAccount.triggerButton')}</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('account.deleteAccount.dialogTitle')}</DialogTitle>
            <DialogDescription>
              {t('account.deleteAccount.dialogDescription', { email })}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm-account-email">{t('account.deleteAccount.emailLabel')}</Label>
            <Input
              id="confirm-account-email"
              value={confirm}
              autoComplete="off"
              onChange={(event) => setConfirm(event.target.value)}
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">{t('common:actions.cancel')}</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={!confirmMatches || pending}
              onClick={() => void onDelete()}
            >
              {t('account.deleteAccount.confirmButton')}
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
  const { t } = useTranslation('settings')
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
    notify.success(t('account.profile.savedToast'))
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
              <FormLabel>{t('account.profile.displayName')}</FormLabel>
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
            {t('common:actions.save')}
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
  const { t } = useTranslation('settings')
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof emailSchema>>({
    resolver: zodResolver(emailSchema),
    defaultValues: { email: '' },
  })

  async function onSubmit(values: z.infer<typeof emailSchema>) {
    setError(null)
    if (values.email === currentEmail) {
      setError(t('account.email.sameError'))
      return
    }
    // GoTrue schickt eine Bestaetigungs-Mail an die NEUE Adresse; die alte
    // bleibt aktiv, bis der Link bestaetigt ist (Re-Confirm).
    const { error: updateError } = await supabase.auth.updateUser({ email: values.email })
    if (updateError) {
      setError(updateError.message)
      return
    }
    notify.success(t('account.email.sentToast'))
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
              <FormLabel>{t('account.email.changeLabel')}</FormLabel>
              <FormControl>
                <Input type="email" autoComplete="email" placeholder={currentEmail} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <p className="text-xs text-muted-foreground">
          {t('account.email.currentNote', { email: currentEmail })}
        </p>
        {error !== null ? <ErrorAlert message={error} /> : null}
        <div>
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={form.formState.isSubmitting}
          >
            {t('account.email.changeButton')}
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
  const { t } = useTranslation('settings')
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
    notify.success(hasPassword ? t('account.password.changedToast') : t('account.password.setToast'))
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
              <FormLabel>{hasPassword ? t('account.password.newLabel') : t('account.password.setLabel')}</FormLabel>
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
              <FormLabel>{t('account.password.confirmLabel')}</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="new-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {!hasPassword ? (
          <p className="text-xs text-muted-foreground">
            {t('account.password.magicLinkHint')}
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
            {hasPassword ? t('account.password.changeButton') : t('account.password.setButton')}
          </Button>
        </div>
      </form>
    </Form>
  )
}

function SignOutEverywhere() {
  const { t } = useTranslation('settings')
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
    notify.success(t('account.signOutEverywhere.successToast'))
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm">
        <div className="font-medium">{t('account.signOutEverywhere.title')}</div>
        <p className="text-muted-foreground">
          {t('account.signOutEverywhere.description')}
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
          {t('account.signOutEverywhere.button')}
        </Button>
      </div>
    </div>
  )
}
