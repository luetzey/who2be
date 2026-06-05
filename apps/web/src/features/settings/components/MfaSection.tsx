import { zodResolver } from '@hookform/resolvers/zod'
import type { Factor } from '@supabase/supabase-js'
import { ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { notify } from '@/lib/feedback'
import { supabase } from '@/lib/supabase'

// Admin-MFA (WP-F, Befund S1): TOTP-Enrollment innerhalb der Konto-Sicherheits-
// Card. Faktoren werden ueber die GoTrue-`/factors`-API (supabase.auth.mfa)
// verwaltet — Enroll → Challenge/Verify → Liste/Unenroll. Nach einer
// verifizierten Challenge traegt das Access-Token `aal=aal2`; das Backend
// erzwingt aal2 fuer Admin-Aktionen (core/security.require_aal2).

const codeSchema = z.object({
  // GoTrue erwartet einen 6-stelligen TOTP-Code.
  code: z
    .string()
    .trim()
    .regex(/^\d{6}$/, 'Bitte einen 6-stelligen Code eingeben.'),
})

type CodeValues = z.infer<typeof codeSchema>

export function MfaSection() {
  const { t } = useTranslation('settings')
  const [factors, setFactors] = useState<Factor[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const { data, error } = await supabase.auth.mfa.listFactors()
    if (error) {
      setLoadError(error.message)
      return
    }
    setLoadError(null)
    setFactors(data?.all ?? [])
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // Nur abgeschlossene (verifizierte) Faktoren zaehlen als aktiver Schutz;
  // unverifizierte Reste eines abgebrochenen Enrollments werden ausgeblendet.
  const verified = factors.filter((factor) => factor.status === 'verified')

  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm">
        <div className="font-medium">{t('account.mfa.title')}</div>
        <p className="text-muted-foreground">{t('account.mfa.description')}</p>
      </div>

      {loadError !== null ? <ErrorAlert message={loadError} /> : null}

      {verified.length > 0 ? (
        <ul className="flex flex-col gap-2" aria-label={t('account.mfa.listLabel')}>
          {verified.map((factor) => (
            <li
              key={factor.id}
              className="flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2">
                <ShieldCheck className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">
                  {factor.friendly_name || t('account.mfa.factorFallbackName')}
                </span>
                <Badge>{t('account.mfa.statusActive')}</Badge>
              </span>
              <RemoveFactorButton factor={factor} onRemoved={refresh} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{t('account.mfa.empty')}</p>
      )}

      <div>
        <EnrollDialog onEnrolled={refresh} />
      </div>
    </div>
  )
}

function EnrollDialog({ onEnrolled }: { onEnrolled: () => Promise<void> }) {
  const { t } = useTranslation('settings')
  const [open, setOpen] = useState(false)
  const [enroll, setEnroll] = useState<{ factorId: string; qr: string; secret: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const form = useForm<CodeValues>({
    resolver: zodResolver(codeSchema),
    defaultValues: { code: '' },
  })

  async function startEnroll() {
    setError(null)
    const { data, error: enrollError } = await supabase.auth.mfa.enroll({ factorType: 'totp' })
    if (enrollError || data === null) {
      setError(enrollError?.message ?? t('account.mfa.enrollError'))
      return
    }
    setEnroll({ factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret })
  }

  async function cleanup() {
    // Best-effort: einen noch unverifizierten Faktor beim Abbrechen wieder
    // entfernen, damit keine verwaisten Enrollments liegen bleiben.
    if (enroll !== null) {
      await supabase.auth.mfa.unenroll({ factorId: enroll.factorId }).catch(() => undefined)
    }
    setEnroll(null)
    setError(null)
    form.reset({ code: '' })
  }

  function onOpenChange(next: boolean) {
    setOpen(next)
    if (next) {
      void startEnroll()
    } else {
      void cleanup()
    }
  }

  async function onVerify(values: CodeValues) {
    if (enroll === null) {
      return
    }
    setError(null)
    const { error: verifyError } = await supabase.auth.mfa.challengeAndVerify({
      factorId: enroll.factorId,
      code: values.code,
    })
    if (verifyError) {
      setError(verifyError.message)
      return
    }
    notify.success(t('account.mfa.enrolledToast'))
    setEnroll(null)
    form.reset({ code: '' })
    setOpen(false)
    await onEnrolled()
  }

  // GoTrue liefert den QR als rohes SVG; als Bildquelle braucht es das
  // data-URI-Praefix (sofern nicht ohnehin schon eines vorhanden ist).
  const qrSrc =
    enroll !== null && !enroll.qr.startsWith('data:')
      ? `data:image/svg+xml;utf-8,${enroll.qr}`
      : (enroll?.qr ?? '')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          {t('account.mfa.addButton')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('account.mfa.enrollTitle')}</DialogTitle>
          <DialogDescription>{t('account.mfa.enrollDescription')}</DialogDescription>
        </DialogHeader>

        {enroll !== null ? (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onVerify)} className="flex flex-col gap-4">
              <img
                src={qrSrc}
                alt={t('account.mfa.qrAlt')}
                className="size-48 self-center rounded-md border bg-card p-2"
              />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">{t('account.mfa.secretLabel')}</span>
                <code className="rounded-sm bg-muted px-2 py-1 font-mono text-xs break-all">
                  {enroll.secret}
                </code>
              </div>
              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('account.mfa.codeLabel')}</FormLabel>
                    <FormControl>
                      <Input
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        placeholder={t('account.mfa.codePlaceholder')}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {error !== null ? <ErrorAlert message={error} /> : null}
              <DialogFooter>
                <DialogClose asChild>
                  <Button type="button" variant="outline">
                    {t('common:actions.cancel')}
                  </Button>
                </DialogClose>
                <Button type="submit" variant="brand" disabled={form.formState.isSubmitting}>
                  {t('account.mfa.verifyButton')}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        ) : (
          <div className="py-6 text-center text-sm text-muted-foreground">
            {error !== null ? <ErrorAlert message={error} /> : t('account.mfa.preparing')}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function RemoveFactorButton({
  factor,
  onRemoved,
}: {
  factor: Factor
  onRemoved: () => Promise<void>
}) {
  const { t } = useTranslation('settings')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onRemove() {
    setPending(true)
    setError(null)
    const { error: removeError } = await supabase.auth.mfa.unenroll({ factorId: factor.id })
    if (removeError) {
      setError(removeError.message)
      setPending(false)
      return
    }
    notify.success(t('account.mfa.removedToast'))
    setPending(false)
    await onRemoved()
  }

  return (
    <Dialog onOpenChange={(next) => !next && setError(null)}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          {t('account.mfa.removeButton')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('account.mfa.removeTitle')}</DialogTitle>
          <DialogDescription>{t('account.mfa.removeDescription')}</DialogDescription>
        </DialogHeader>
        {error !== null ? <ErrorAlert message={error} /> : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={pending}
            onClick={() => void onRemove()}
          >
            {t('account.mfa.removeConfirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
