import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function SelectShowcase() {
  return (
    <ShowcaseSection
      id="select"
      title="Select"
      description="Natives Single-Choice-Control fuer kompakte Picker (z.B. Rollen). Immer mit Label."
    >
      <ShowcaseRow label="Default">
        <div className="flex w-full max-w-sm flex-col gap-2">
          <Label htmlFor="catalog-select-default">Rolle</Label>
          <Select id="catalog-select-default" defaultValue="editor">
            <option value="admin">Admin</option>
            <option value="editor">Editor</option>
            <option value="viewer">Viewer</option>
          </Select>
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="Disabled">
        <div className="flex w-full max-w-sm flex-col gap-2">
          <Label htmlFor="catalog-select-disabled">Rolle</Label>
          <Select id="catalog-select-disabled" defaultValue="viewer" disabled>
            <option value="viewer">Viewer</option>
          </Select>
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
