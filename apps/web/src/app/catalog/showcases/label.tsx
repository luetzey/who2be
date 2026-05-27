import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function LabelShowcase() {
  return (
    <ShowcaseSection
      id="label"
      title="Label"
      description="Beschriftung fuer Form-Felder. Setzt htmlFor (oder steht in <FormField>)."
    >
      <ShowcaseRow label="Default">
        <div className="flex w-full max-w-sm flex-col gap-2">
          <Label htmlFor="catalog-label-name">Name</Label>
          <Input id="catalog-label-name" placeholder="Eintragen…" />
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
