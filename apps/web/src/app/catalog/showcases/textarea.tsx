import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function TextareaShowcase() {
  return (
    <ShowcaseSection
      id="textarea"
      title="Textarea"
      description="Multi-Line-Eingabe fuer Beschreibungen, Persona-Body, Playbook-Content."
    >
      <ShowcaseRow label="Default">
        <div className="flex w-full max-w-md flex-col gap-2">
          <Label htmlFor="catalog-textarea-default">Beschreibung</Label>
          <Textarea
            id="catalog-textarea-default"
            placeholder="Kurze Beschreibung der Persona…"
            rows={4}
          />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="Disabled">
        <div className="flex w-full max-w-md flex-col gap-2">
          <Label htmlFor="catalog-textarea-disabled">Read-only</Label>
          <Textarea id="catalog-textarea-disabled" disabled defaultValue="Nicht editierbar." />
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
