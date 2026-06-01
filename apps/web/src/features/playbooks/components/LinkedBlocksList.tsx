import type { LinkAvailability, ResourceLink } from '@/api/types'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface LinkedBlocksListProps {
  links: ResourceLink[]
  // Optional: ohne Handler wird die Entfernen-Aktion ausgeblendet (read-only,
  // z. B. wenn die Relationen im BlockNote-Body als Pills gepflegt werden).
  onRemove?: (link: ResourceLink) => void
  disabled?: boolean
}

interface AvailabilityMeta {
  label: string
  variant: BadgeProps['variant']
  empty: string
}

const META: Record<'active' | 'draft' | 'deleted', AvailabilityMeta> = {
  active: { label: 'Aktiv', variant: 'secondary', empty: '(leer)' },
  draft: { label: 'Nur in Draft', variant: 'outline', empty: '(leer — Draft)' },
  deleted: {
    label: 'Block geloescht',
    variant: 'destructive',
    empty: 'Block nicht mehr verfuegbar',
  },
}

const RESOURCE_SCOPE_META: AvailabilityMeta = {
  label: 'Ganzes Dokument',
  variant: 'secondary',
  empty: 'Resource nicht mehr verfuegbar',
}

// Backend liefert ab Track A `available_in: 'active' | 'draft' | null`. Bis
// dahin lesen wir das alte `available`-Boolean (true → 'active', false →
// geloescht). So bleibt der Frontend-Build stabil, egal welche Backend-
// Version laeuft.
function resolveAvailability(link: ResourceLink): 'active' | 'draft' | 'deleted' {
  const fromNew: LinkAvailability | undefined = link.available_in
  if (fromNew === undefined) {
    return link.available ? 'active' : 'deleted'
  }
  if (fromNew === 'active') return 'active'
  if (fromNew === 'draft') return 'draft'
  return 'deleted'
}

export function LinkedBlocksList({ links, onRemove, disabled = false }: LinkedBlocksListProps) {
  if (links.length === 0) {
    return <p className="text-sm text-muted-foreground">Noch keine Bloecke verknuepft.</p>
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Verknuepfte Bloecke">
      {links.map((link) => {
        const isResourceScope = link.link_scope === 'resource'
        const state = resolveAvailability(link)
        const meta = isResourceScope
          ? state === 'deleted'
            ? META.deleted
            : RESOURCE_SCOPE_META
          : META[state]
        const preview = link.section_preview ?? link.preview
        const subline = isResourceScope
          ? 'Vollstaendige Resource referenziert'
          : state === 'deleted'
            ? meta.empty
            : (preview ?? meta.empty)
        return (
          <li
            key={`${link.resource_id}-${link.link_scope ?? 'block'}-${link.block_id ?? 'resource'}`}
            className="flex items-center justify-between gap-3 rounded-md border p-3"
          >
            <span className="flex min-w-0 flex-col gap-1">
              <span className="text-sm font-medium">{link.resource_name}</span>
              <span className="truncate text-xs text-muted-foreground">{subline}</span>
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <Badge variant={meta.variant}>{meta.label}</Badge>
              {onRemove !== undefined ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemove(link)}
                  disabled={disabled}
                >
                  Entfernen
                </Button>
              ) : null}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
