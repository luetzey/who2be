// PlaybookPicker — Dialog mit Combobox-Suche ueber api.listPlaybooks().
// Liefert bei Bestaetiung ein PlaceholderProps-Objekt via onConfirm-Callback.
import { useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import type { Playbook } from '@/api/types'
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

interface PlaybookPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
}

export function PlaybookPicker({ open, onConfirm, onCancel }: PlaybookPickerProps) {
  const api = useApi()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Playbook | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setQuery('')
    setSelected(null)
    api
      .listPlaybooks()
      .then(setPlaybooks)
      .catch(() => setPlaybooks([]))
      .finally(() => setLoading(false))
  }, [open, api])

  const filtered = query.trim() === ''
    ? playbooks
    : playbooks.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))

  function handleConfirm() {
    if (selected === null) return
    onConfirm({
      kind: 'playbook',
      target_id: selected.id,
      label: `Playbook: ${selected.name}`,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel() }}>
      <DialogContent data-testid="playbook-picker-dialog">
        <DialogHeader>
          <DialogTitle>Playbook verlinken</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Suchen…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            data-testid="playbook-picker-search"
          />
          <div className="max-h-64 overflow-y-auto rounded-md border">
            {loading ? (
              <p className="p-3 text-sm text-muted-foreground">Lade…</p>
            ) : filtered.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground">Keine Playbooks gefunden.</p>
            ) : (
              <ul role="listbox" aria-label="Playbook-Liste">
                {filtered.map((p) => (
                  <li key={p.id} role="option" aria-selected={selected?.id === p.id}>
                    <Button
                      variant={selected?.id === p.id ? 'secondary' : 'ghost'}
                      className="w-full justify-start rounded-none"
                      onClick={() => setSelected(p)}
                      data-testid={`playbook-option-${p.id}`}
                    >
                      {p.name}
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
            data-testid="playbook-picker-confirm"
          >
            Einfuegen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
