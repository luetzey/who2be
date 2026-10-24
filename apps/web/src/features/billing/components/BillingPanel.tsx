import type { TFunction } from 'i18next'
import { AlertCircle } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import '../i18n'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert, LoadingState } from '@/components/data'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { formatDate } from '@/lib/dates'

import { useCheckout } from '../hooks/useCheckout'
import { useEntitlement } from '../hooks/useEntitlement'

import { BillingDetailsForm, BillingDetailsSummary, useBillingProfile } from './BillingDetailsForm'
import { InvoiceListCard } from './InvoiceList'

interface BillingTier {
  code: string
  name: string
  priceEur: number
  mcpMonthlyQuota: number
  mcpRatePerMin: number
  /** `null` = unbegrenzt. */
  entityLimit: number | null
}

/**
 * Tarif-Stammdaten fuer die Darstellung (Issue #449, `docs/licensing/plans.md`).
 * `EntitlementInfo` (`apps/web/src/api/types.ts`) liefert nur die durchgesetzten
 * Groessen (`mcp_monthly_quota`, `mcp_rate_per_min`) — Preis und Entity-Limit
 * kommen vom Backend nicht mit, deshalb dupliziert diese Liste sie bewusst.
 * Quellen, die bei einer Preis-/Limit-Aenderung zuerst anzupassen sind:
 *   - Preis, MCP/Monat, MCP/min: `packages/billing/src/who2be_billing/plans.py`
 *     (`FREE_PLAN`, `PRO_PLAN`)
 *   - Entity-Limit: `apps/api/src/who2be_api/licensing/entitlement.py`
 *     (`FREE_ENTITY_QUOTA`, `Entitlement.entity_limit`)
 * Ein dritter Tarif ist ein weiterer Eintrag hier — kein Umbau des Panels: die
 * aktive Zeile wird ueber `mcp_monthly_quota` gegen diese Liste erkannt (siehe
 * `findTier` unten), nicht ueber Feature-Codes. "Ist bezahlt?" (siehe `isPaid`
 * in `BillingPanel`) ist bewusst ein separater, tolerantere Schwellwert-Check —
 * ein `manual_override`-Entitlement (docs/licensing/plans.md,
 * `POST .../billing/override`) traegt keine der beiden exakten Quoten hier.
 */
const TIERS: readonly BillingTier[] = [
  { code: 'free', name: 'Free', priceEur: 0, mcpMonthlyQuota: 1_000, mcpRatePerMin: 30, entityLimit: 50 },
  { code: 'pro', name: 'Pro', priceEur: 9.99, mcpMonthlyQuota: 100_000, mcpRatePerMin: 240, entityLimit: null },
]

const FREE_QUOTA = TIERS[0].mcpMonthlyQuota

function findTier(mcpMonthlyQuota: number | null): BillingTier | undefined {
  return TIERS.find((tier) => tier.mcpMonthlyQuota === mcpMonthlyQuota)
}

function formatPrice(t: TFunction, tier: BillingTier | undefined): string {
  if (!tier) return t('panel.plan.unknown')
  return tier.priceEur === 0
    ? t('panel.price.free')
    : t('panel.price.perMonth', { amount: tier.priceEur })
}

function formatEntityLimit(t: TFunction, tier: BillingTier | undefined): string {
  if (!tier) return t('panel.plan.unknown')
  return tier.entityLimit === null ? t('panel.unlimited') : String(tier.entityLimit)
}

function formatExpiry(iso: string | null, unlimited: string): string {
  if (!iso) return unlimited
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : formatDate(date)
}

/**
 * Bytes in eine lesbare Groesse (Issue #536). Binaere Einheiten, weil die
 * Konstanten binaer sind (`FREE_STORAGE_QUOTA_BYTES = 100 * 1024 * 1024`) —
 * eine dezimale Anzeige wuerde „100 MB" als „104,9 MB" zeigen.
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const rounded = value >= 10 || Number.isInteger(value) ? Math.round(value) : Math.round(value * 10) / 10
  return `${rounded} ${units[unit]}`
}

function StorageBar({ usedBytes, quotaBytes }: { usedBytes: number; quotaBytes: number | null }) {
  const { t } = useTranslation('billing')
  if (quotaBytes === null) {
    return <p className="text-sm text-muted-foreground">{t('panel.storage.unlimited')}</p>
  }
  const ratio = quotaBytes > 0 ? Math.min(1, usedBytes / quotaBytes) : 1
  const percent = Math.round(ratio * 100)
  const exhausted = usedBytes >= quotaBytes
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="min-w-0 truncate text-muted-foreground">{t('panel.storage.label')}</span>
        <span className="shrink-0 font-medium tabular-nums">
          {formatBytes(usedBytes)} / {formatBytes(quotaBytes)}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={exhausted ? 'h-full bg-destructive' : 'h-full bg-primary'}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={usedBytes}
          aria-valuemin={0}
          aria-valuemax={quotaBytes}
          aria-label={t('panel.storage.ariaLabel')}
          data-testid="storage-bar"
        />
      </div>
    </div>
  )
}

function QuotaBar({ count, quota }: { count: number; quota: number | null }) {
  const { t } = useTranslation('billing')
  if (quota === null) {
    return <p className="text-sm text-muted-foreground">{t('panel.quota.unlimited')}</p>
  }
  const ratio = quota > 0 ? Math.min(1, count / quota) : 1
  const percent = Math.round(ratio * 100)
  const exhausted = count >= quota
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="min-w-0 truncate text-muted-foreground">
          {t('panel.quota.monthlyLabel')}
        </span>
        <span className="shrink-0 font-medium tabular-nums">
          {count} / {quota}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={exhausted ? 'h-full bg-destructive' : 'h-full bg-primary'}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={count}
          aria-valuemin={0}
          aria-valuemax={quota}
          aria-label={t('panel.quota.ariaLabel')}
          data-testid="mcp-quota-bar"
        />
      </div>
    </div>
  )
}

/**
 * Anker der Rechnungsdaten-Karte: die 409-Meldung des Checkouts springt dorthin.
 */
const BILLING_DETAILS_ID = 'billing-details'

/**
 * 409 vom Checkout (R2c): der Server kennt keine Rechnungsdaten der Org. Das
 * passiert, wenn der Client einen veralteten Stand zeigt (z. B. in einem
 * zweiten Tab geloescht). Statt der rohen Servermeldung eine eigene Meldung
 * mit Sprung zur Rechnungsdaten-Karte aus R1.
 */
function DetailsMissingAlert({ canJump }: { canJump: boolean }) {
  const { t } = useTranslation('billing')
  const jump = () => {
    const card = document.getElementById(BILLING_DETAILS_ID)
    if (!card) return
    card.scrollIntoView?.({ block: 'start' })
    card.focus()
  }
  return (
    <Alert variant="destructive" data-testid="checkout-details-missing">
      <AlertCircle />
      <AlertTitle>{t('error.detailsMissing.title')}</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{t('error.detailsMissing.message')}</p>
        {canJump ? (
          <Button variant="outline" className="h-10 w-full sm:w-auto" onClick={jump}>
            {t('error.detailsMissing.action')}
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}

/**
 * Billing-Slot der Org-Settings (Track D). Bewusst **cloud-only**: in der
 * On-Prem-Edition liefert der Endpoint `edition='onprem'` und das Panel rendert
 * `null` — On-Prem ist unbegrenzt und ohne Billing. Zeigt Plan-Status, Features,
 * MCP-Kontingent/Verbrauch und einen Upgrade-CTA.
 *
 * Darunter fuer Admins die Rechnungsdaten (ADR-0061 R1). Solange keine
 * gespeichert sind, bleibt der Upgrade-Knopf gesperrt: eine Rechnung nach §14
 * UStG braucht Name und Adresse. Der Checkout sperrt serverseitig ebenfalls
 * (409, R2c); die Meldung dazu verweist auf die Rechnungsdaten-Karte. Fuer
 * Nicht-Admins aendert sich nichts (der Checkout ist ohnehin admin-only).
 *
 * Ganz unten fuer Admins die Rechnungen mit PDF-Download (ADR-0061 R3). Die
 * Karte erscheint nur hier, also nur in der Cloud-Edition.
 */
export function BillingPanel() {
  const { t } = useTranslation('billing')
  const { data, loading, error, notFound } = useEntitlement()
  const checkout = useCheckout()
  const isAdmin = useCurrentWorkspaceRole() === 'admin'
  const details = useBillingProfile(isAdmin && data?.edition === 'cloud')

  if (loading) return <LoadingState />
  if (notFound) return null
  if (error) return <ErrorAlert message={error} />
  if (!data) return null
  // On-Prem/OSS: kein Billing-Slot.
  if (data.edition !== 'cloud') return null

  const active = data.status === 'active'
  // Zwei getrennte Fragen mit unterschiedlichem Robustheits-Bedarf:
  //  - "Ist bezahlt?" (`isPaid`, steuert den CTA) ist ein Schwellwert: alles
  //    oberhalb der Free-Quota zaehlt, `null` (unbegrenzt, z. B. `signed_license`/
  //    `OSS_ENTITLEMENT`) ebenfalls. Ein `manual_override`-Entitlement mit
  //    individueller Quota (docs/licensing/plans.md) ist damit korrekt bezahlt,
  //    auch ohne exakten Tier-Treffer.
  //  - "Welcher Tarif genau?" (`tier`, steuert nur die Anzeige von Name/Preis/
  //    Entity-Limit) bleibt ein exakter Match; ohne Treffer zeigt die Anzeige
  //    `panel.plan.unknown`.
  const quota = data.mcp_monthly_quota
  const isPaid = active && (quota === null || quota > FREE_QUOTA)
  const tier = findTier(quota)
  // Upgrade erst mit gespeicherten Rechnungsdaten (nur Admins laden sie).
  const detailsMissing = isAdmin && (details.loading || !details.data?.profile)

  return (
    <div className="flex min-w-0 flex-col gap-4">
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="min-w-0 truncate">{t('panel.title')}</CardTitle>
          <Badge className="shrink-0" variant={active ? 'default' : 'destructive'}>
            {active ? t('panel.statusActive') : t('panel.statusInactive')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <QuotaBar count={data.usage.count} quota={data.mcp_monthly_quota} />
        <StorageBar
          usedBytes={data.usage.storage_bytes}
          quotaBytes={data.storage_quota_bytes}
        />

        <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
          <dt className="text-muted-foreground">{t('panel.plan.label')}</dt>
          <dd className="text-right font-medium">{tier?.name ?? t('panel.plan.unknown')}</dd>
          <dt className="text-muted-foreground">{t('panel.plan.priceLabel')}</dt>
          <dd className="text-right font-medium">{formatPrice(t, tier)}</dd>
          <dt className="text-muted-foreground">{t('panel.rateLimit')}</dt>
          <dd className="text-right font-medium tabular-nums">
            {data.mcp_rate_per_min === null ? t('panel.unlimited') : `${data.mcp_rate_per_min}/min`}
          </dd>
          <dt className="text-muted-foreground">{t('panel.plan.entityLimitLabel')}</dt>
          <dd className="text-right font-medium tabular-nums">{formatEntityLimit(t, tier)}</dd>
          <dt className="text-muted-foreground">{t('panel.plan.tokenQuotaLabel')}</dt>
          <dd className="text-right font-medium tabular-nums">
            {data.token_quota === null ? t('panel.unlimited') : String(data.token_quota)}
          </dd>
          <dt className="text-muted-foreground">{t('panel.plan.workspaceQuotaLabel')}</dt>
          <dd className="text-right font-medium tabular-nums">
            {data.workspace_quota === null ? t('panel.unlimited') : String(data.workspace_quota)}
          </dd>
          <dt className="text-muted-foreground">{t('panel.validUntil')}</dt>
          <dd className="text-right font-medium">{formatExpiry(data.expires_at, t('expiry.unlimited'))}</dd>
        </dl>

        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{t('panel.features.label')}</p>
          <div className="flex flex-wrap gap-1.5">
            {data.features.length === 0 ? (
              <span className="text-sm text-muted-foreground">{t('panel.features.none')}</span>
            ) : (
              data.features.map((feature) => (
                <Badge key={feature} variant="secondary">
                  {feature}
                </Badge>
              ))
            )}
          </div>
        </div>

        {isPaid ? (
          <Button className="w-full" disabled>
            {t('panel.proActive', { plan: tier?.name ?? t('panel.plan.unknown') })}
          </Button>
        ) : (
          <>
            <Button
              className="w-full"
              disabled={checkout.pending || detailsMissing}
              aria-describedby={detailsMissing ? 'billing-upgrade-hint' : undefined}
              onClick={() => checkout.start('pro')}
            >
              {checkout.pending ? t('panel.upgrading') : t('panel.upgrade')}
            </Button>
            {detailsMissing && !details.loading ? (
              <p id="billing-upgrade-hint" className="text-sm text-muted-foreground">
                {t('details.requiredForUpgrade')}
              </p>
            ) : null}
          </>
        )}
        {checkout.errorStatus === 409 ? (
          <DetailsMissingAlert canJump={isAdmin} />
        ) : checkout.error ? (
          <ErrorAlert message={checkout.error} />
        ) : null}
      </CardContent>
    </Card>
    {isAdmin ? <BillingDetailsCard details={details} /> : null}
    {isAdmin ? <InvoiceListCard /> : null}
    </div>
  )
}

/**
 * Rechnungsdaten-Karte: Formular, solange nichts gespeichert ist oder der
 * Admin bearbeitet, sonst die Zusammenfassung mit „Bearbeiten“.
 */
function BillingDetailsCard({ details }: { details: ReturnType<typeof useBillingProfile> }) {
  const { t } = useTranslation('billing')
  const [editing, setEditing] = useState(false)
  const profile = details.data?.profile ?? null

  return (
    <Card id={BILLING_DETAILS_ID} tabIndex={-1} className="scroll-mt-4">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="min-w-0 truncate">{t('details.title')}</CardTitle>
          {profile && !editing ? (
            <Button variant="outline" className="h-10 shrink-0" onClick={() => setEditing(true)}>
              {t('details.edit')}
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {details.loading ? (
          <LoadingState />
        ) : details.error || !details.data ? (
          <ErrorAlert message={details.error ?? t('common:errors.unknown')} />
        ) : profile && !editing ? (
          <BillingDetailsSummary profile={profile} />
        ) : (
          <>
            <p className="text-sm text-muted-foreground">{t('details.intro')}</p>
            <BillingDetailsForm
              response={details.data}
              saving={details.saving}
              saveError={details.saveError}
              onCancel={profile ? () => setEditing(false) : undefined}
              onSubmit={async (input) => {
                const ok = await details.save(input)
                if (ok) setEditing(false)
                return ok
              }}
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}
