import { useTranslation } from 'react-i18next'

import '../i18n'

import { ErrorAlert, LoadingState } from '@/components/data'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui'

import { useCheckout } from '../hooks/useCheckout'
import { useEntitlement } from '../hooks/useEntitlement'

// Feature-Codes, die den Pro-Tier ausmachen (siehe docs/licensing/plans.md).
const PRO_FEATURES = ['composite_playbooks', 'agents', 'audit_export']

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
  // Pro-Tier liegt vor, wenn alle Pro-Feature-Codes aktiv freigeschaltet sind.
  const isPro = active && PRO_FEATURES.every((feature) => data.features.includes(feature))

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
          <dt className="text-muted-foreground">{t('panel.rateLimit')}</dt>
          <dd className="text-right font-medium tabular-nums">
            {data.mcp_rate_per_min === null ? t('panel.unlimited') : `${data.mcp_rate_per_min}/min`}
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

        {isPro ? (
          <Button className="w-full" disabled>
            {t('panel.proActive')}
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
