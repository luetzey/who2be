// useResourceSearch — kapselt das Laden + Filtern der Resource-Liste und
// (bei aktivem Block-Anker) der Heading-Bloecke fuer den ResourcePicker.
// Haelt `useApi()` aus der Praesentations-Komponente heraus (Frontend-Standard:
// Datenholen gehoert nicht in tief verschachtelte UI). Verhalten unveraendert
// uebernommen aus dem vorherigen ResourcePicker (inkl. der `if (!open) return`-
// Guards gegen setState->Re-Render->Effect-Schleifen bei instabiler `api`-Ref).
import { useEffect, useState } from 'react'

import type { Resource, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'

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

export interface UseResourceSearch {
  query: string
  setQuery: (query: string) => void
  selected: Resource | null
  setSelected: (resource: Resource | null) => void
  loading: boolean
  filtered: Resource[]
  selectedBlockId: string | null
  setSelectedBlockId: (blockId: string | null) => void
  blocksLoading: boolean
  headingBlocks: ResourceBlock[]
  headingTitle: (block: ResourceBlock) => string
}

export function useResourceSearch(
  open: boolean,
  allowBlockAnchor: boolean,
  initialTargetId: string | undefined,
): UseResourceSearch {
  const api = useApi()
  const [resources, setResources] = useState<Resource[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Resource | null>(null)
  const [loading, setLoading] = useState(false)

  // Block-Anker-State (nur bei allowBlockAnchor relevant).
  const [blocks, setBlocks] = useState<ResourceBlock[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [blocksLoading, setBlocksLoading] = useState(false)

  // Edit-Modus: target_id in Resource-UUID + optionalen Block-Anker zerlegen.
  const hashIndex = initialTargetId !== undefined ? initialTargetId.indexOf('#') : -1
  const initialResourceId =
    initialTargetId === undefined
      ? undefined
      : hashIndex >= 0
        ? initialTargetId.slice(0, hashIndex)
        : initialTargetId
  const initialBlockId =
    initialTargetId !== undefined && hashIndex >= 0
      ? initialTargetId.slice(hashIndex + 1)
      : undefined

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setQuery('')
    setBlocks([])
    setSelectedBlockId(null)
    api
      .listResources()
      .then((list) => {
        setResources(list)
        setSelected(
          initialResourceId !== undefined
            ? (list.find((r) => r.id === initialResourceId) ?? null)
            : null,
        )
      })
      .catch(() => {
        setResources([])
        setSelected(null)
      })
      .finally(() => setLoading(false))
  }, [open, api, initialResourceId])

  // Bei Resource-Wahl (und aktivem Block-Anker) die Heading-Bloecke laden.
  // `if (!open) return` analog zum Resource-Lade-Effect oben: ohne diesen
  // Guard liefe der Effect auch bei geschlossenem Picker und loeste bei einer
  // instabilen `api`-Referenz (Render-zu-Render neues Objekt) eine
  // setState->Re-Render->Effect-Schleife aus.
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
      .then((full) => {
        setBlocks(full.content.blocks ?? [])
        // Edit-Modus: Anker nur fuer die urspruenglich referenzierte Resource
        // vorbelegen (bei Wechsel auf eine andere Resource bleibt er leer).
        if (initialBlockId !== undefined && selected.id === initialResourceId) {
          setSelectedBlockId(initialBlockId)
        }
      })
      .catch(() => setBlocks([]))
      .finally(() => setBlocksLoading(false))
  }, [open, allowBlockAnchor, selected, api, initialBlockId, initialResourceId])

  const filtered =
    query.trim() === ''
      ? resources
      : resources.filter((r) => r.name.toLowerCase().includes(query.toLowerCase()))

  const headingBlocks = blocks.filter(isHeadingBlock)

  function headingTitle(block: ResourceBlock): string {
    const text = blockPlainText(block).trim()
    return text.length > 0 ? text : '(unbenanntes Heading)'
  }

  return {
    query,
    setQuery,
    selected,
    setSelected,
    loading,
    filtered,
    selectedBlockId,
    setSelectedBlockId,
    blocksLoading,
    headingBlocks,
    headingTitle,
  }
}
