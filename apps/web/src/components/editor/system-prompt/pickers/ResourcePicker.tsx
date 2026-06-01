// ResourcePicker — Dialog mit Combobox-Suche ueber api.listResources().
// Analog zu PlaybookPicker.
//
// Additiv (Playbook-Body-Welle): mit `allowBlockAnchor` zeigt der Picker
// nach der Resource-Wahl eine optionale Heading-Block-Auswahl (Section-
// Anker). Wird ein Heading gewaehlt, liefert `onConfirm` ein
// `target_id="<uuid>#<block_id>"` und ein Label `"Resource: Name › Heading"`.
// Ohne `allowBlockAnchor` (Default, System-Prompt-Editor) bleibt das
// Verhalten unveraendert: ganze Resource, `target_id="<uuid>"`.
import { useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import type { Resource, ResourceBlock } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

import type { PlaceholderProps } from '../PlaceholderBlock'

interface ResourcePickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /**
   * Additiv: erlaubt die Auswahl eines Heading-Block-Ankers innerhalb der
   * gewaehlten Resource. Default `false` (System-Prompt-Editor verlinkt nur
   * die ganze Resource).
   */
  allowBlockAnchor?: boolean
}

// Lokaler Heading-Detektor + Plain-Text-Extraktor (kein Feature-Import, damit
// der geteilte Editor nicht auf `features/playbooks` koppelt). BlockNote-
// Headings sind `type==='heading'` (props.level) oder Legacy `heading_*`.
function isHeadingBlock(block: ResourceBlock): boolean {
  if (block.type === 'heading') return true
  return typeof block.type === 'string' && block.type.startsWith('heading_')
}

function blockPlainText(block: ResourceBlock): string {
  const parts: string[] = []
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) {
      node.forEach(walk)
      return
    }
    if (node !== null && typeof node === 'object') {
      const record = node as Record<string, unknown>
      if (typeof record.text === 'string') parts.push(record.text)
      walk(record.content)
      walk(record.children)
    }
  }
  walk((block as Record<string, unknown>).content)
  walk((block as Record<string, unknown>).children)
  return parts.join('')
}

export function ResourcePicker({
  open,
  onConfirm,
  onCancel,
  allowBlockAnchor = false,
}: ResourcePickerProps) {
  const api = useApi()
  const [resources, setResources] = useState<Resource[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Resource | null>(null)
  const [loading, setLoading] = useState(false)

  // Block-Anker-State (nur bei allowBlockAnchor relevant).
  const [blocks, setBlocks] = useState<ResourceBlock[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [blocksLoading, setBlocksLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setQuery('')
    setSelected(null)
    setBlocks([])
    setSelectedBlockId(null)
    api
      .listResources()
      .then(setResources)
      .catch(() => setResources([]))
      .finally(() => setLoading(false))
  }, [open, api])

  // Bei Resource-Wahl (und aktivem Block-Anker) die Heading-Bloecke laden.
  // `if (!open) return` analog zum Resource-Lade-Effect oben: ohne diesen
  // Guard liefe der Effect auch bei geschlossenem Picker und loeste bei einer
  // instabilen `api`-Referenz (Render-zu-Render neues Objekt) eine
  // setState→Re-Render→Effect-Schleife aus.
  useEffect(() => {
    if (!open) return
    if (!allowBlockAnchor || selected === null) {
      setBlocks([])
      setSelectedBlockId(null)
      return
    }
    setBlocksLoading(true)
    setSelectedBlockId(null)
    api
      .getResource(selected.id)
      .then((full) => setBlocks(full.content.blocks ?? []))
      .catch(() => setBlocks([]))
      .finally(() => setBlocksLoading(false))
  }, [open, allowBlockAnchor, selected, api])

  const filtered =
    query.trim() === ''
      ? resources
      : resources.filter((r) => r.name.toLowerCase().includes(query.toLowerCase()))

  const headingBlocks = blocks.filter(isHeadingBlock)

  function headingTitle(block: ResourceBlock): string {
    const text = blockPlainText(block).trim()
    return text.length > 0 ? text : '(unbenanntes Heading)'
  }

  function handleConfirm() {
    if (selected === null) return
    if (allowBlockAnchor && selectedBlockId !== null) {
      const heading = headingBlocks.find((b) => b.id === selectedBlockId)
      const title = heading !== undefined ? headingTitle(heading) : selectedBlockId
      onConfirm({
        kind: 'resource',
        target_id: `${selected.id}#${selectedBlockId}`,
        label: `Resource: ${selected.name} › ${title}`,
      })
      return
    }
    onConfirm({
      kind: 'resource',
      target_id: selected.id,
      label: `Resource: ${selected.name}`,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel() }}>
      <DialogContent data-testid="resource-picker-dialog">
        <DialogHeader>
          <DialogTitle>Resource verlinken</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Suchen…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            data-testid="resource-picker-search"
          />
          <div className="max-h-64 overflow-y-auto rounded-md border">
            {loading ? (
              <p className="p-3 text-sm text-muted-foreground">Lade…</p>
            ) : filtered.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground">Keine Resources gefunden.</p>
            ) : (
              <ul role="listbox" aria-label="Resource-Liste">
                {filtered.map((r) => (
                  <li key={r.id} role="option" aria-selected={selected?.id === r.id}>
                    <Button
                      variant={selected?.id === r.id ? 'secondary' : 'ghost'}
                      className="w-full justify-start rounded-none"
                      onClick={() => setSelected(r)}
                      data-testid={`resource-option-${r.id}`}
                    >
                      {r.name}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Optionaler Block-Anker: Heading-Bloecke der gewaehlten Resource. */}
          {allowBlockAnchor && selected !== null ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Optional: Section verlinken
              </p>
              <div className="max-h-48 overflow-y-auto rounded-md border">
                {blocksLoading ? (
                  <p className="p-3 text-sm text-muted-foreground">Lade Bloecke…</p>
                ) : headingBlocks.length === 0 ? (
                  <p className="p-3 text-sm text-muted-foreground">
                    Keine Heading-Bloecke — die ganze Resource wird verlinkt.
                  </p>
                ) : (
                  <ul role="listbox" aria-label="Heading-Bloecke">
                    <li role="option" aria-selected={selectedBlockId === null}>
                      <Button
                        variant={selectedBlockId === null ? 'secondary' : 'ghost'}
                        className="w-full justify-start rounded-none"
                        onClick={() => setSelectedBlockId(null)}
                        data-testid="resource-block-option-whole"
                      >
                        Gesamtes Dokument
                      </Button>
                    </li>
                    {headingBlocks.map((block) => (
                      <li
                        key={block.id}
                        role="option"
                        aria-selected={selectedBlockId === block.id}
                      >
                        <Button
                          variant={selectedBlockId === block.id ? 'secondary' : 'ghost'}
                          className="w-full justify-start rounded-none"
                          onClick={() => setSelectedBlockId(block.id)}
                          data-testid={`resource-block-option-${block.id}`}
                        >
                          {headingTitle(block)}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Abbrechen
          </Button>
          <Button
            variant="brand"
            disabled={selected === null}
            onClick={handleConfirm}
            data-testid="resource-picker-confirm"
          >
            Einfuegen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
