import { Badge } from '@/components/ui/badge'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function BadgeShowcase() {
  return (
    <ShowcaseSection
      id="badge"
      title="Badge"
      description="Inline-Marker fuer Status, Tags, Versionen. Varianten: default, secondary, destructive, outline."
    >
      <ShowcaseRow label="Varianten">
        <Badge>Default</Badge>
        <Badge variant="secondary">Secondary</Badge>
        <Badge variant="destructive">Destructive</Badge>
        <Badge variant="outline">Outline</Badge>
      </ShowcaseRow>
      <ShowcaseRow label="Inhalt">
        <Badge>v1.4.0</Badge>
        <Badge variant="secondary">Draft</Badge>
        <Badge variant="destructive">Revoked</Badge>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
