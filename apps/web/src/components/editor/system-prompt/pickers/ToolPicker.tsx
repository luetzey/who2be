// ToolPicker — schwebendes Popover mit Combobox-Suche ueber die aktiven
// External-Tools des Workspace (api.listExternalTools, WP-4). Anders als
// PlaybookPicker/ResourcePicker referenziert die Pill NICHT die UUID des
// Aggregats, sondern den stabilen Faehigkeits-Alias
// (`target_id = tool.alias`) — ein Re-Binding auf ein neues Tool-Objekt unter
// demselben Alias bricht die Referenz nicht (Blueprint-Entscheidung 4,
// `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type AnchorRef } from '@/components/ui/popover'

import { useToolSearch } from '../hooks/useToolSearch'
import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'
import { useTranslation } from 'react-i18next'

interface ToolPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /**
   * Edit-Modus: vorhandene Pill-Werte. `target_id` ist der Alias; ist gesetzt,
   * wird das referenzierte Tool vorselektiert und der Confirm-Button heisst
   * „Aktualisieren".
   */
  initial?: PlaceholderProps
}

export function ToolPicker({ open, onConfirm, onCancel, anchorRef, initial }: ToolPickerProps) {
  const { t } = useTranslation('editor')
  const isEdit = initial !== undefined
  const { query, setQuery, selected, setSelected, loading, filtered } = useToolSearch(
    open,
    initial?.target_id,
  )

  function handleConfirm() {
    if (selected === null) return
    const displayName = selected.content.display_name || selected.name
    onConfirm({
      kind: 'tool-ref',
      target_id: selected.alias,
      label: `Tool: ${displayName}`,
    })
  }

  return (
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? t('picker.tool.titleEdit') : t('picker.tool.titleNew')}
      ariaLabel={t('picker.tool.ariaLabel')}
      testId="tool-picker-dialog"
    >
      <Input
        placeholder={t('picker.searchPlaceholder')}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        data-testid="tool-picker-search"
      />
      <div className="max-h-64 overflow-y-auto rounded-md border">
        {loading ? (
          <p className="p-3 text-sm text-muted-foreground">{t('picker.loading')}</p>
        ) : filtered.length === 0 ? (
          <p className="p-3 text-sm text-muted-foreground">
            {t('picker.tool.empty')}
          </p>
        ) : (
          <ul role="listbox" aria-label={t('picker.tool.listLabel')}>
            {filtered.map((tool) => (
              <li key={tool.id} role="option" aria-selected={selected?.alias === tool.alias}>
                <Button
                  variant={selected?.alias === tool.alias ? 'secondary' : 'ghost'}
                  className="w-full justify-start rounded-none"
                  onClick={() => setSelected(tool)}
                  data-testid={`tool-option-${tool.alias}`}
                >
                  <span className="flex flex-col items-start">
                    <span>{tool.name}</span>
                    <span className="text-xs text-muted-foreground">{tool.alias}</span>
                  </span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          {t('picker.cancel')}
        </Button>
        <Button
          variant="brand"
          disabled={selected === null}
          onClick={handleConfirm}
          data-testid="tool-picker-confirm"
        >
          {isEdit ? t('picker.update') : t('picker.insert')}
        </Button>
      </div>
    </PickerPopover>
  )
}
