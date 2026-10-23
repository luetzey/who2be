import { zodResolver } from '@hookform/resolvers/zod'
import type { TFunction } from 'i18next'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import '../i18n'

import type {
  BillingProfile,
  BillingProfileInput,
  BillingProfileResponse,
  BillingVatStatus,
} from '@/api/client'
import { useApi } from '@/api/useApi'
import { ErrorAlert } from '@/components/data'
import {
  Badge,
  Button,
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  Input,
  Label,
  Select,
} from '@/components/ui'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import i18n from '@/i18n'

// --- Hook --------------------------------------------------------------------

interface UseBillingProfileResult {
  data: BillingProfileResponse | null
  loading: boolean
  error: string | null
  save: (input: BillingProfileInput) => Promise<boolean>
  saving: boolean
  saveError: string | null
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

/**
 * Laedt und speichert die Rechnungsdaten der Organisation (ADR-0061 R1).
 * `enabled=false` (kein Admin) laedt nichts: der Endpoint ist admin-only.
 * Die Antwort ist die eine Quelle der Ansicht — nach dem Speichern ersetzt
 * die Server-Antwort den Stand, kein lokales Zusammenbauen.
 */
export function useBillingProfile(enabled: boolean): UseBillingProfileResult {
  const api = useApi()
  const [data, setData] = useState<BillingProfileResponse | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getBillingProfile()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describeError(cause))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, enabled])

  const save = useCallback(
    async (input: BillingProfileInput) => {
      setSaving(true)
      setSaveError(null)
      try {
        setData(await api.saveBillingProfile(input))
        return true
      } catch (cause: unknown) {
        setSaveError(describeError(cause))
        return false
      } finally {
        setSaving(false)
      }
    },
    [api],
  )

  return { data, loading, error, save, saving, saveError }
}

// --- Validierung ---------------------------------------------------------------

/** Laenderpraefix der USt-IdNr.; Griechenland fuehrt in VIES `EL`. */
function vatPrefix(country: string): string {
  return country === 'GR' ? 'EL' : country
}

/** Gleiche Normalform wie der Server: gross, ohne Leerzeichen, Punkte, Striche. */
function normalizeVatId(raw: string): string {
  return raw.replace(/[\s.-]/g, '').toUpperCase()
}

const VAT_ID_PATTERN = /^[A-Z]{2}[A-Z0-9]{2,13}$/

/**
 * Die USt-IdNr. gilt nur bei Firma + EU-Land. Eine Quelle fuer Anzeige,
 * Validierung und `toInput`, damit ein ausgeblendetes Feld nie mitzaehlt.
 */
function vatVisible(customerType: string, country: string, euCountries: Set<string>): boolean {
  return customerType === 'business' && euCountries.has(country)
}

const formSchemaShape = {
  customer_type: z.enum(['business', 'consumer']),
  given_name: z.string(),
  family_name: z.string(),
  company_name: z.string(),
  street: z.string(),
  postal_code: z.string(),
  city: z.string(),
  country: z.string(),
  vat_id: z.string(),
}

type FormValues = z.infer<z.ZodObject<typeof formSchemaShape>>

/**
 * Vorab-Pruefung im Client, dieselben Regeln wie `BillingProfileInput` im
 * Server (der verbindlich bleibt). Die Laenderlisten kommen vom Server.
 */
function makeSchema(t: TFunction, countries: Set<string>, euCountries: Set<string>) {
  const required = t('details.validation.required')
  return z.object(formSchemaShape).superRefine((values, ctx) => {
    const need = (path: keyof FormValues, max: number) => {
      const value = values[path].trim()
      if (value === '') ctx.addIssue({ code: 'custom', path: [path], message: required })
      else if (value.length > max) {
        ctx.addIssue({ code: 'custom', path: [path], message: t('details.validation.tooLong', { max }) })
      }
    }
    if (values.customer_type === 'consumer') {
      need('given_name', 100)
      need('family_name', 100)
    } else {
      need('company_name', 200)
    }
    need('street', 200)
    need('postal_code', 20)
    need('city', 100)
    if (!countries.has(values.country)) {
      ctx.addIssue({ code: 'custom', path: ['country'], message: required })
    }
    // Das Feld steht nur bei Firma + EU-Land im Formular (`vatVisible`). Ist es
    // ausgeblendet, zaehlt ein Rest-Wert im Form-State nicht: sonst laege der
    // Fehler auf einem unsichtbaren Feld und das Speichern scheiterte stumm.
    const vat = normalizeVatId(values.vat_id)
    if (vatVisible(values.customer_type, values.country, euCountries) && vat !== '') {
      if (!VAT_ID_PATTERN.test(vat)) {
        ctx.addIssue({ code: 'custom', path: ['vat_id'], message: t('details.validation.vatFormat') })
      } else if (!vat.startsWith(vatPrefix(values.country))) {
        ctx.addIssue({
          code: 'custom',
          path: ['vat_id'],
          message: t('details.validation.vatPrefix', { prefix: vatPrefix(values.country) }),
        })
      }
    }
  })
}

function toInput(values: FormValues, euCountries: Set<string>): BillingProfileInput {
  const consumer = values.customer_type === 'consumer'
  const opt = (value: string) => (value.trim() === '' ? null : value.trim())
  const vat = vatVisible(values.customer_type, values.country, euCountries)
    ? normalizeVatId(values.vat_id)
    : ''
  return {
    customer_type: values.customer_type,
    given_name: consumer ? opt(values.given_name) : null,
    family_name: consumer ? opt(values.family_name) : null,
    company_name: consumer ? null : opt(values.company_name),
    street: values.street.trim(),
    postal_code: values.postal_code.trim(),
    city: values.city.trim(),
    country: values.country,
    vat_id: consumer || vat === '' ? null : vat,
  }
}

function toValues(profile: BillingProfile | null): FormValues {
  return {
    customer_type: profile?.customer_type ?? 'business',
    given_name: profile?.given_name ?? '',
    family_name: profile?.family_name ?? '',
    company_name: profile?.company_name ?? '',
    street: profile?.street ?? '',
    postal_code: profile?.postal_code ?? '',
    city: profile?.city ?? '',
    country: profile?.country ?? '',
    vat_id: profile?.vat_id ?? '',
  }
}

/** Laendernamen in der UI-Sprache, alphabetisch; Fallback ist der Code. */
function useCountryOptions(codes: string[]): Array<{ code: string; name: string }> {
  const language = i18n.resolvedLanguage ?? i18n.language ?? 'de'
  return useMemo(() => {
    let names: Intl.DisplayNames | null = null
    try {
      names = new Intl.DisplayNames([language], { type: 'region' })
    } catch {
      names = null
    }
    return codes
      .map((code) => ({ code, name: names?.of(code) ?? code }))
      .sort((a, b) => a.name.localeCompare(b.name, language))
  }, [codes, language])
}

// --- Anzeige ------------------------------------------------------------------

function VatStatusBadge({ status }: { status: BillingVatStatus }) {
  const { t } = useTranslation('billing')
  const variant = status === 'valid' ? 'default' : status === 'invalid' ? 'destructive' : 'secondary'
  return (
    <Badge className="shrink-0" variant={variant}>
      {t(`details.vatStatus.${status}`)}
    </Badge>
  )
}

/** Gespeicherte Rechnungsdaten als kompakte Zusammenfassung. */
export function BillingDetailsSummary({ profile }: { profile: BillingProfile }) {
  const { t } = useTranslation('billing')
  const [country] = useCountryOptions(useMemo(() => [profile.country], [profile.country]))
  const name =
    profile.customer_type === 'business'
      ? profile.company_name
      : `${profile.given_name ?? ''} ${profile.family_name ?? ''}`.trim()
  return (
    <div className="min-w-0 space-y-1 text-sm" data-testid="billing-details-summary">
      <p className="truncate font-medium">{name}</p>
      <p className="break-words text-muted-foreground">
        {profile.street}, {profile.postal_code} {profile.city}, {country?.name ?? profile.country}
      </p>
      {profile.vat_id && profile.vat_status ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="min-w-0 break-all text-muted-foreground">
            {t('details.fields.vatId')}: {profile.vat_id}
          </span>
          <VatStatusBadge status={profile.vat_status} />
        </div>
      ) : null}
    </div>
  )
}

// --- Formular -----------------------------------------------------------------

interface BillingDetailsFormProps {
  response: BillingProfileResponse
  saving: boolean
  saveError: string | null
  onSubmit: (input: BillingProfileInput) => Promise<boolean>
  onCancel?: () => void
}

/**
 * Formular fuer die Rechnungsdaten (ADR-0061 R1, §14 UStG). Pflichtfelder
 * haengen am Kundentyp: Privat = Vor- und Nachname, Firma = Firmenname und
 * optional die USt-IdNr. (nur EU). Die USt-IdNr. prueft der Server bei VIES;
 * ein VIES-Ausfall blockiert das Speichern nicht, die Nummer steht dann als
 * „ungeprueft“ da.
 */
export function BillingDetailsForm({
  response,
  saving,
  saveError,
  onSubmit,
  onCancel,
}: BillingDetailsFormProps) {
  const { t } = useTranslation('billing')
  const countries = useMemo(() => new Set(response.countries), [response.countries])
  const euCountries = useMemo(() => new Set(response.eu_countries), [response.eu_countries])
  const options = useCountryOptions(response.countries)
  const schema = useMemo(() => makeSchema(t, countries, euCountries), [t, countries, euCountries])

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: toValues(response.profile),
  })
  const customerType = form.watch('customer_type')
  const country = form.watch('country')
  const showVat = vatVisible(customerType, country, euCountries)

  async function submit(values: FormValues) {
    // `saving` sperrt den Knopf; der Guard faengt den Doppel-Submit per Enter.
    if (saving) return
    await onSubmit(toInput(values, euCountries))
  }

  const text = (
    name: 'given_name' | 'family_name' | 'company_name' | 'street' | 'postal_code' | 'city',
    autoComplete: string,
  ) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem className="min-w-0">
          <FormLabel>{t(`details.fields.${name}`)}</FormLabel>
          <FormControl>
            <Input autoComplete={autoComplete} required {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(submit)}
        className="flex min-w-0 flex-col gap-4"
        aria-label={t('details.title')}
        noValidate
      >
        <FormField
          control={form.control}
          name="customer_type"
          render={({ field }) => (
            <fieldset className="flex min-w-0 flex-col gap-2">
              <legend className="mb-2 text-sm font-medium">{t('details.fields.customer_type')}</legend>
              <RadioGroup
                value={field.value}
                onValueChange={(next) => field.onChange(next)}
                className="flex flex-wrap gap-4"
              >
                {(['business', 'consumer'] as const).map((type) => (
                  <div key={type} className="flex items-center gap-2">
                    <RadioGroupItem value={type} id={`billing-customer-${type}`} />
                    <Label htmlFor={`billing-customer-${type}`} className="font-normal">
                      {t(`details.customerType.${type}`)}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </fieldset>
          )}
        />

        {customerType === 'consumer' ? (
          <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
            {text('given_name', 'given-name')}
            {text('family_name', 'family-name')}
          </div>
        ) : (
          text('company_name', 'organization')
        )}

        {text('street', 'street-address')}
        <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)]">
          {text('postal_code', 'postal-code')}
          {text('city', 'address-level2')}
        </div>

        <FormField
          control={form.control}
          name="country"
          render={({ field }) => (
            <FormItem className="min-w-0">
              <FormLabel>{t('details.fields.country')}</FormLabel>
              <FormControl>
                <Select autoComplete="country" required {...field}>
                  <option value="">{t('details.countryPlaceholder')}</option>
                  {options.map((option) => (
                    <option key={option.code} value={option.code}>
                      {option.name}
                    </option>
                  ))}
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {showVat ? (
          <FormField
            control={form.control}
            name="vat_id"
            render={({ field }) => (
              <FormItem className="min-w-0">
                <FormLabel>{t('details.fields.vatIdOptional')}</FormLabel>
                <FormControl>
                  <Input
                    autoComplete="off"
                    spellCheck={false}
                    placeholder={t('details.vatPlaceholder', { prefix: vatPrefix(country) })}
                    {...field}
                  />
                </FormControl>
                <p className="text-sm text-muted-foreground">{t('details.vatHelp')}</p>
                <FormMessage />
              </FormItem>
            )}
          />
        ) : null}

        {saveError ? <ErrorAlert message={saveError} /> : null}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {onCancel ? (
            <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={saving}>
              {t('details.cancel')}
            </Button>
          ) : null}
          <Button type="submit" className="h-10" disabled={saving}>
            {saving ? t('details.saving') : t('details.save')}
          </Button>
        </div>
      </form>
    </Form>
  )
}
