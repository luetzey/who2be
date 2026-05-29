import type { ResourceLink } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface LinkedBlocksListProps {
  links: ResourceLink[]
  onRemove: (link: ResourceLink) => void
  disabled?: boolean
}

export function LinkedBlocksList({ links, onRemove, disabled = false }: LinkedBlocksListProps) {
  if (links.length === 0) {
    return <p className="text-sm text-muted-foreground">Noch keine Bloecke verknuepft.</p>
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Verknuepfte Bloecke">
      {links.map((link) => (
        <li
          key={`${link.resource_id}-${link.block_id}`}
          className="flex items-center justify-between gap-3 rounded-md border p-3"
        >
          <span className="flex min-w-0 flex-col gap-1">
            <span className="text-sm font-medium">{link.resource_name}</span>
            <span className="truncate text-xs text-muted-foreground">
              {link.available ? (link.preview ?? '(leer)') : 'Block nicht mehr verfuegbar'}
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-2">
            <Badge variant={link.available ? 'secondary' : 'destructive'}>
              {link.available ? 'Verfuegbar' : 'Block geloescht'}
            </Badge>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onRemove(link)}
              disabled={disabled}
            >
              Entfernen
            </Button>
          </span>
        </li>
      ))}
    </ul>
  )
}
