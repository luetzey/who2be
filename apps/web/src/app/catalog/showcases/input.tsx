import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function InputShowcase() {
  return (
    <ShowcaseSection
      id="input"
      title="Input"
      description="Text-Input fuer Single-Line-Eingaben. Immer mit zugehoerigem Label."
    >
      <ShowcaseRow label="Default">
        <div className="flex w-full max-w-sm flex-col gap-2">
          <Label htmlFor="catalog-input-default">Name</Label>
          <Input id="catalog-input-default" placeholder="z.B. Persona-Slug" />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="Disabled">
        <div className="flex w-full max-w-sm flex-col gap-2">
          <Label htmlFor="catalog-input-disabled">Slug</Label>
          <Input id="catalog-input-disabled" placeholder="readonly" disabled />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="Invalid (aria-invalid)">
        <div className="flex w-full max-w-sm flex-col gap-2">
          <Label htmlFor="catalog-input-invalid">E-Mail</Label>
          <Input
            id="catalog-input-invalid"
            type="email"
            defaultValue="ungueltig"
            aria-invalid="true"
          />
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
