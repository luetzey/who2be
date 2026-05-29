import { useCallback, useEffect, useState } from 'react'

import type { Resource, ResourceBlock, ResourceLink, ResourceLinkItemInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

import { blockPreview } from '../lib/blockText'

interface ResourceBlockLinkPickerProps {
  existing: ResourceLink[]
  saving: boolean
  onSave: (items: ResourceLinkItemInput[]) => void | Promise<void>
}

function keyOf(resourceId: string, blockId: string): string {
  return `${resourceId}::${blockId}`
}

export function ResourceBlockLinkPicker({
  existing,
  saving,
  onSave,
}: ResourceBlockLinkPickerProps) {
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [resources, setResources] = useState<Resource[]>([])
  const [activeResource, setActiveResource] = useState<Resource | null>(null)
  const [blocks, setBlocks] = useState<ResourceBlock[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Beim Oeffnen: aktuelle Auswahl aus den bestehenden Links uebernehmen und
  // die Resource-Liste laden.
  useEffect(() => {
    if (!open) {
      return
    }
    setSelected(existing.map((link) => keyOf(link.resource_id, link.block_id)))
    setLoadError(null)
    api
      .listResources()
      .then(setResources)
      .catch((cause: unknown) =>
        setLoadError(cause instanceof Error ? cause.message : 'Laden fehlgeschlagen.'),
      )
  }, [open, existing, api])

  const openResource = useCallback(
    (resource: Resource) => {
      setActiveResource(resource)
      api
        .getResource(resource.id)
        .then((full) => setBlocks(full.content.blocks ?? []))
        .catch((cause: unknown) =>
          setLoadError(cause instanceof Error ? cause.message : 'Laden fehlgeschlagen.'),
        )
    },
    [api],
  )

  const toggle = useCallback((key: string) => {
    setSelected((current) =>
      current.includes(key) ? current.filter((entry) => entry !== key) : [...current, key],
    )
  }, [])

  const handleSave = useCallback(async () => {
    const items: ResourceLinkItemInput[] = selected.map((key, index) => {
      const [resourceId, blockId] = key.split('::')
      return { resource_id: resourceId, block_id: blockId, position: index }
    })
    await onSave(items)
    setOpen(false)
  }, [selected, onSave])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          Bloecke verknuepfen
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Resource-Bloecke verknuepfen</DialogTitle>
          <DialogDescription>
            Waehle links eine Resource und rechts die zu verknuepfenden Bloecke.
          </DialogDescription>
        </DialogHeader>

        {loadError !== null ? (
          <p className="text-sm text-destructive">{loadError}</p>
        ) : null}

        <div className="grid grid-cols-2 gap-4">
          <ul className="flex max-h-80 flex-col gap-1 overflow-auto" aria-label="Resources">
            {resources.map((resource) => (
              <li key={resource.id}>
                <Button
                  type="button"
                  variant="ghost"
                  className={cn(
                    'w-full justify-start',
                    activeResource?.id === resource.id && 'bg-accent text-accent-foreground',
                  )}
                  onClick={() => openResource(resource)}
                >
                  {resource.name}
                </Button>
              </li>
            ))}
            {resources.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">Keine Resources.</li>
            ) : null}
          </ul>

          <ul className="flex max-h-80 flex-col gap-2 overflow-auto" aria-label="Bloecke">
            {activeResource === null ? (
              <li className="px-1 text-sm text-muted-foreground">
                Resource waehlen, um Bloecke zu sehen.
              </li>
            ) : (
              blocks.map((block) => {
                const key = keyOf(activeResource.id, block.id)
                return (
                  <li key={block.id} className="flex items-start gap-3 rounded-md border p-2">
                    <Checkbox
                      id={`block-${block.id}`}
                      checked={selected.includes(key)}
                      onChange={() => toggle(key)}
                      aria-label={`Block ${block.id} verknuepfen`}
                    />
                    <Label htmlFor={`block-${block.id}`} className="text-sm font-normal">
                      {blockPreview(block)}
                    </Label>
                  </li>
                )
              })
            )}
            {activeResource !== null && blocks.length === 0 ? (
              <li className="px-1 text-sm text-muted-foreground">Keine Bloecke.</li>
            ) : null}
          </ul>
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Abbrechen
          </Button>
          <Button type="button" variant="brand" onClick={() => void handleSave()} disabled={saving}>
            Speichern ({selected.length})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
