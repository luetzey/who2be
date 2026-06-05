// ResourcePicker — Dialog mit Combobox-Suche ueber api.listResources().
// Analog zu PlaybookPicker. Daten-/Block-Anker-Logik liegt im Hook
// `useResourceSearch`; diese Komponente bleibt reine Praesentation.
//
// Additiv (Playbook-Body-Welle): mit `allowBlockAnchor` zeigt der Picker
// nach der Resource-Wahl eine optionale Heading-Block-Auswahl (Section-
// Anker). Wird ein Heading gewaehlt, liefert `onConfirm` ein
// `target_id="<uuid>#<block_id>"` und ein Label `"Resource: Name › Heading"`.
// Ohne `allowBlockAnchor` (Default, System-Prompt-Editor) bleibt das
// Verhalten unveraendert: ganze Resource, `target_id="<uuid>"`.
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type AnchorRef } from '@/components/ui/popover'

import { useResourceSearch } from '../hooks/useResourceSearch'
import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'

interface ResourcePickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /**
   * Additiv: erlaubt die Auswahl eines Heading-Block-Ankers innerhalb der
   * gewaehlten Resource. Default `false` (System-Prompt-Editor verlinkt nur
   * die ganze Resource).
   */
  allowBlockAnchor?: boolean
  /**
   * Edit-Modus: vorhandene Pill-Werte. `target_id` kann `<uuid>` oder
   * `<uuid>#<block_id>` sein; Resource (und ggf. Section-Anker) werden
   * vorselektiert, der Confirm-Button heisst „Aktualisieren".
   */
  initial?: PlaceholderProps
}

export function ResourcePicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  allowBlockAnchor = false,
  initial,
}: ResourcePickerProps) {
  const isEdit = initial !== undefined
  const {
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
  } = useResourceSearch(open, allowBlockAnchor, initial?.target_id)

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
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? 'Resource ändern' : 'Resource verlinken'}
      ariaLabel="Resource verlinken"
      testId="resource-picker-dialog"
    >
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
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button
          variant="brand"
          disabled={selected === null}
          onClick={handleConfirm}
          data-testid="resource-picker-confirm"
        >
          {isEdit ? 'Aktualisieren' : 'Einfuegen'}
        </Button>
      </div>
    </PickerPopover>
  )
}
