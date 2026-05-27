import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function ButtonShowcase() {
  return (
    <ShowcaseSection
      id="button"
      title="Button"
      description="cva-Varianten: brand, default, destructive, outline, secondary, ghost, link. Groessen: default, sm, lg, icon."
    >
      <ShowcaseRow label="Varianten">
        <Button variant="brand">Brand</Button>
        <Button>Default</Button>
        <Button variant="destructive">Destructive</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="link">Link</Button>
      </ShowcaseRow>
      <ShowcaseRow label="Groessen">
        <Button size="sm">Small</Button>
        <Button size="default">Default</Button>
        <Button size="lg">Large</Button>
        <Button size="icon" aria-label="Hinzufuegen">
          <Plus />
        </Button>
      </ShowcaseRow>
      <ShowcaseRow label="Disabled">
        <Button disabled>Default</Button>
        <Button variant="outline" disabled>
          Outline
        </Button>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
