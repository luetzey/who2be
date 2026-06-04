import { useCallback, useEffect, useMemo, useState } from 'react'

import type {
  EmbeddingMode,
  Resource,
  ResourceBlock,
  ResourceLink,
  ResourceLinkItemInput,
} from '@/api/types'
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

import { blockPlainText, isHeadingBlock, sectionPreview } from '../lib/blockText'

interface ResourceBlockLinkPickerProps {
  existing: ResourceLink[]
  saving: boolean
  onSave: (items: ResourceLinkItemInput[]) => void | Promise<void>
}

// Selektions-Keys: Block-Anker ueber `<resourceId>::<blockId>`, ein
// 'resource'-Scope-Eintrag ueber `<resourceId>::__resource__`. So
// laufen beide Modi durch dasselbe Toggle-Array, und die exklusive
// Disable-Logik im Picker bleibt auf eine Lookup-Map reduziert.
const RESOURCE_SCOPE_TOKEN = '__resource__'

function blockKeyOf(resourceId: string, blockId: string): string {
  return `${resourceId}::${blockId}`
}

function resourceScopeKeyOf(resourceId: string): string {
  return `${resourceId}::${RESOURCE_SCOPE_TOKEN}`
}

function headingText(block: ResourceBlock): string {
  const text = blockPlainText(block).trim()
  return text.length > 0 ? text : '(unbenanntes Heading)'
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
  // Embed-Modus je Volldokument-Ref (key = resourceId). Default 'lazy':
  // der MCP sendet das Dokument NICHT inline mit. Nur fuer 'resource'-scope
  // relevant — Block-Anker bleiben immer Pointer.
  const [modes, setModes] = useState<Record<string, EmbeddingMode>>({})
  const [loadError, setLoadError] = useState<string | null>(null)

  // Beim Oeffnen: aktuelle Auswahl aus den bestehenden Links uebernehmen und
  // die Resource-Liste laden. 'resource'-Scope-Links werden auf den
  // Resource-Token gemapped, Block-Scope-Links auf den Block-Anker.
  useEffect(() => {
    if (!open) {
      return
    }
    setSelected(
      existing.map((link) =>
        link.link_scope === 'resource' || link.block_id === null
          ? resourceScopeKeyOf(link.resource_id)
          : blockKeyOf(link.resource_id, link.block_id),
      ),
    )
    setModes(
      Object.fromEntries(
        existing
          .filter((link) => link.link_scope === 'resource' || link.block_id === null)
          .map((link) => [link.resource_id, link.embedding_mode ?? 'lazy']),
      ),
    )
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

  // 'Gesamtes Dokument' fuer die aktive Resource togglen — exklusive
  // Logik (Block-Auswahl derselben Resource wird beim Aktivieren entfernt,
  // damit der Backend-Constraint nicht doppelt feuert).
  const toggleResourceScope = useCallback((resourceId: string) => {
    const key = resourceScopeKeyOf(resourceId)
    const prefix = `${resourceId}::`
    setSelected((current) => {
      if (current.includes(key)) {
        return current.filter((entry) => entry !== key)
      }
      return [
        ...current.filter((entry) => !entry.startsWith(prefix)),
        key,
      ]
    })
  }, [])

  const setMode = useCallback((resourceId: string, mode: EmbeddingMode) => {
    setModes((current) => ({ ...current, [resourceId]: mode }))
  }, [])

  const handleSave = useCallback(async () => {
    const items: ResourceLinkItemInput[] = selected.map((key, index) => {
      const [resourceId, anchor] = key.split('::')
      if (anchor === RESOURCE_SCOPE_TOKEN) {
        return {
          resource_id: resourceId,
          block_id: null,
          position: index,
          link_scope: 'resource',
          embedding_mode: modes[resourceId] ?? 'lazy',
        }
      }
      return {
        resource_id: resourceId,
        block_id: anchor,
        position: index,
        link_scope: 'block',
      }
    })
    await onSave(items)
    setOpen(false)
  }, [selected, modes, onSave])

  // Phase 3-B: nur Heading-Bloecke sind als Anker erlaubt — Backend
  // (Track A) erzwingt das ebenfalls.
  const headingBlocks = blocks.filter(isHeadingBlock)

  const resourceScopeSelected = useMemo(() => {
    if (activeResource === null) return false
    return selected.includes(resourceScopeKeyOf(activeResource.id))
  }, [activeResource, selected])

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
            Waehle links eine Resource und rechts den Heading-Block, dessen Section
            verlinkt werden soll. Nur Heading-Bloecke sind als Anker erlaubt.
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

          <div className="flex max-h-80 flex-col gap-3 overflow-auto">
            {activeResource === null ? (
              <p className="px-1 text-sm text-muted-foreground">
                Resource waehlen, um Heading-Bloecke zu sehen.
              </p>
            ) : (
              <>
                <div className="flex items-start gap-3 rounded-md border border-dashed p-2">
                  <Checkbox
                    id={`resource-${activeResource.id}`}
                    checked={resourceScopeSelected}
                    onChange={() => toggleResourceScope(activeResource.id)}
                    aria-label="Gesamtes Dokument verknuepfen"
                  />
                  <div className="flex flex-1 flex-col gap-1">
                    <Label
                      htmlFor={`resource-${activeResource.id}`}
                      className="flex flex-col gap-1 text-sm font-normal"
                    >
                      <span className="font-medium">Gesamtes Dokument</span>
                      <span className="text-xs text-muted-foreground">
                        Verlinkt die komplette Resource — exklusive zu
                        einzelnen Block-Ankern.
                      </span>
                    </Label>
                    {resourceScopeSelected ? (
                      <span
                        className="mt-1 inline-flex w-fit overflow-hidden rounded-md border"
                        role="group"
                        aria-label="Embed-Modus fuer das gesamte Dokument"
                      >
                        <Button
                          type="button"
                          variant={
                            (modes[activeResource.id] ?? 'lazy') === 'lazy' ? 'brand' : 'ghost'
                          }
                          size="sm"
                          className="h-6 rounded-none px-2 text-xs"
                          onClick={() => setMode(activeResource.id, 'lazy')}
                          aria-pressed={(modes[activeResource.id] ?? 'lazy') === 'lazy'}
                        >
                          Link (lazy)
                        </Button>
                        <Button
                          type="button"
                          variant={
                            (modes[activeResource.id] ?? 'lazy') === 'inline' ? 'brand' : 'ghost'
                          }
                          size="sm"
                          className="h-6 rounded-none px-2 text-xs"
                          onClick={() => setMode(activeResource.id, 'inline')}
                          aria-pressed={(modes[activeResource.id] ?? 'lazy') === 'inline'}
                        >
                          Fest einbetten
                        </Button>
                      </span>
                    ) : null}
                  </div>
                </div>
                <ul
                  className={cn(
                    'flex flex-col gap-2',
                    resourceScopeSelected && 'pointer-events-none opacity-60',
                  )}
                  aria-label="Heading-Bloecke"
                >
                  {headingBlocks.length === 0 ? (
                    <li className="px-1 text-sm text-muted-foreground">
                      Diese Resource hat keine Heading-Bloecke.
                    </li>
                  ) : (
                    headingBlocks.map((block) => {
                      const key = blockKeyOf(activeResource.id, block.id)
                      const preview = sectionPreview(blocks, block.id)
                      return (
                        <li
                          key={block.id}
                          className="flex items-start gap-3 rounded-md border p-2"
                        >
                          <Checkbox
                            id={`block-${block.id}`}
                            checked={selected.includes(key)}
                            onChange={() => toggle(key)}
                            disabled={resourceScopeSelected}
                            aria-label={`Section ${headingText(block)} verknuepfen`}
                          />
                          <Label
                            htmlFor={`block-${block.id}`}
                            className="flex flex-col gap-1 text-sm font-normal"
                          >
                            <span className="font-medium">{headingText(block)}</span>
                            {preview.length > 0 ? (
                              <span className="text-xs text-muted-foreground">{preview}</span>
                            ) : (
                              <span className="text-xs text-muted-foreground/70">
                                (leere Section)
                              </span>
                            )}
                          </Label>
                        </li>
                      )
                    })
                  )}
                </ul>
              </>
            )}
          </div>
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
