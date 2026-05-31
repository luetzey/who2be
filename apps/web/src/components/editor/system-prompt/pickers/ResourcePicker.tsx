// ResourcePicker — Dialog mit Combobox-Suche ueber api.listResources().
// Analog zu PlaybookPicker.
import { useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import type { Resource } from '@/api/types'
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
}

export function ResourcePicker({ open, onConfirm, onCancel }: ResourcePickerProps) {
  const api = useApi()
  const [resources, setResources] = useState<Resource[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Resource | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setQuery('')
    setSelected(null)
    api
      .listResources()
      .then(setResources)
      .catch(() => setResources([]))
      .finally(() => setLoading(false))
  }, [open, api])

  const filtered =
    query.trim() === ''
      ? resources
      : resources.filter((r) => r.name.toLowerCase().includes(query.toLowerCase()))

  function handleConfirm() {
    if (selected === null) return
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
