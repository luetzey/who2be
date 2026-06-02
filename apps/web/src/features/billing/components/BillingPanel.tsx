import { ErrorAlert, LoadingState } from '@/components/data'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui'

import { useEntitlement } from '../hooks/useEntitlement'

function formatExpiry(iso: string | null): string {
  if (!iso) return 'unbegrenzt'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString()
}

function QuotaBar({ count, quota }: { count: number; quota: number | null }) {
  if (quota === null) {
    return <p className="text-sm text-muted-foreground">MCP-Kontingent: unbegrenzt</p>
  }
  const ratio = quota > 0 ? Math.min(1, count / quota) : 1
  const percent = Math.round(ratio * 100)
  const exhausted = count >= quota
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">MCP-Reads diesen Monat</span>
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
          aria-label="MCP-Kontingent-Verbrauch"
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
  const { data, loading, error, notFound } = useEntitlement()

  if (loading) return <LoadingState />
  if (notFound) return null
  if (error) return <ErrorAlert message={error} />
  if (!data) return null
  // On-Prem/OSS: kein Billing-Slot.
  if (data.edition !== 'cloud') return null

  const active = data.status === 'active'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>Plan &amp; Nutzung</CardTitle>
          <Badge variant={active ? 'default' : 'destructive'}>
            {active ? 'Aktiv' : 'Inaktiv'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <QuotaBar count={data.usage.count} quota={data.mcp_monthly_quota} />

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Rate-Limit</dt>
          <dd className="text-right font-medium tabular-nums">
            {data.mcp_rate_per_min === null ? 'unbegrenzt' : `${data.mcp_rate_per_min}/min`}
          </dd>
          <dt className="text-muted-foreground">Gueltig bis</dt>
          <dd className="text-right font-medium">{formatExpiry(data.expires_at)}</dd>
        </dl>

        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">Features</p>
          <div className="flex flex-wrap gap-1.5">
            {data.features.length === 0 ? (
              <span className="text-sm text-muted-foreground">keine</span>
            ) : (
              data.features.map((feature) => (
                <Badge key={feature} variant="secondary">
                  {feature}
                </Badge>
              ))
            )}
          </div>
        </div>

        <Button className="w-full" disabled={!active && data.features.length === 0}>
          {active ? 'Plan verwalten' : 'Jetzt upgraden'}
        </Button>
      </CardContent>
    </Card>
  )
}
