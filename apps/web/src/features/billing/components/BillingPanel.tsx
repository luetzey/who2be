import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import '../i18n'

import { ErrorAlert, LoadingState } from '@/components/data'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui'

import { useCheckout } from '../hooks/useCheckout'
import { useEntitlement } from '../hooks/useEntitlement'

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
  { code: 'pro', name: 'Pro', priceEur: 29, mcpMonthlyQuota: 100_000, mcpRatePerMin: 240, entityLimit: null },
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
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString()
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
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{t('panel.quota.monthlyLabel')}</span>
        <span className="font-medium tabular-nums">
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
        />
      </div>
    </div>
  )
}

/**
 * Billing-Slot der Org-Settings (Track D). Bewusst **cloud-only**: in der
 * On-Prem-Edition liefert der Endpoint `edition='onprem'` und das Panel rendert
 * `null` — On-Prem ist unbegrenzt und ohne Billing. Zeigt Plan-Status, Features,
 * MCP-Kontingent/Verbrauch und einen Upgrade-CTA.
 */
export function BillingPanel() {
  const { t } = useTranslation('billing')
  const { data, loading, error, notFound } = useEntitlement()
  const checkout = useCheckout()

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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>{t('panel.title')}</CardTitle>
          <Badge variant={active ? 'default' : 'destructive'}>
            {active ? t('panel.statusActive') : t('panel.statusInactive')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <QuotaBar count={data.usage.count} quota={data.mcp_monthly_quota} />

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
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
          <Button
            className="w-full"
            disabled={checkout.pending}
            onClick={() => checkout.start('pro')}
          >
            {checkout.pending ? t('panel.upgrading') : t('panel.upgrade')}
          </Button>
        )}
        {checkout.error ? <ErrorAlert message={checkout.error} /> : null}
      </CardContent>
    </Card>
  )
}
