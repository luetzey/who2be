import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function CheckboxShowcase() {
  return (
    <ShowcaseSection
      id="checkbox"
      title="Checkbox"
      description="Boolesche Auswahl. Immer mit zugeordnetem Label."
    >
      <ShowcaseRow label="States">
        <div className="flex items-center gap-2">
          <Checkbox id="catalog-cb-unchecked" />
          <Label htmlFor="catalog-cb-unchecked">Unchecked</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="catalog-cb-checked" defaultChecked />
          <Label htmlFor="catalog-cb-checked">Checked (default)</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="catalog-cb-disabled" disabled />
          <Label htmlFor="catalog-cb-disabled">Disabled</Label>
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
