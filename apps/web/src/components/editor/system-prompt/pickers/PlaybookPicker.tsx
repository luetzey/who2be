// PlaybookPicker — schwebendes Popover mit Combobox-Suche ueber
// api.listPlaybooks(). Liefert bei Bestaetigung ein PlaceholderProps-Objekt
// via onConfirm-Callback.
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type AnchorRef } from '@/components/ui/popover'

import { usePlaybookSearch } from '../hooks/usePlaybookSearch'
import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'

interface PlaybookPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /**
   * Edit-Modus: vorhandene Pill-Werte. Ist gesetzt, wird das referenzierte
   * Playbook vorselektiert und der Confirm-Button heisst „Aktualisieren".
   */
  initial?: PlaceholderProps
}

export function PlaybookPicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  initial,
}: PlaybookPickerProps) {
  const isEdit = initial !== undefined
  const { query, setQuery, selected, setSelected, loading, filtered } = usePlaybookSearch(
    open,
    initial?.target_id,
  )

  function handleConfirm() {
    if (selected === null) return
    onConfirm({
      kind: 'playbook',
      target_id: selected.id,
      label: `Playbook: ${selected.name}`,
    })
  }

  return (
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? 'Playbook ändern' : 'Playbook verlinken'}
      ariaLabel="Playbook verlinken"
      testId="playbook-picker-dialog"
    >
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
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button
          variant="brand"
          disabled={selected === null}
          onClick={handleConfirm}
          data-testid="playbook-picker-confirm"
        >
          {isEdit ? 'Aktualisieren' : 'Einfuegen'}
        </Button>
      </div>
    </PickerPopover>
  )
}
