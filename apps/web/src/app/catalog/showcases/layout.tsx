import { Button } from '@/components/ui/button'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Section } from '@/components/layout/Section'
import { Stack } from '@/components/layout/Stack'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

const STACK_GAPS = ['xs', 'sm', 'md', 'lg', 'xl'] as const

export function LayoutShowcase() {
  return (
    <ShowcaseSection
      id="layout"
      title="Layout-Primitives"
      description="Container, PageHeader, Section und Stack — die strukturellen Bausteine fuer Pages."
    >
      <ShowcaseRow label="Container (max-w-5xl + Padding)">
        <Container className="border bg-muted/30 py-3">
          <span className="text-sm text-muted-foreground">Container-Inhalt</span>
        </Container>
      </ShowcaseRow>
      <ShowcaseRow label="PageHeader">
        <div className="w-full">
          <PageHeader
            title="Personas"
            description="Versionierte Persona-Definitionen."
            actions={<Button size="sm">Neu</Button>}
          />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="Section (aria-label)">
        <Section ariaLabel="Demo-Section" className="w-full rounded-md border bg-muted/20 p-4">
          <p className="text-sm">Section gruppiert verwandte Inhalte und setzt aria-label.</p>
        </Section>
      </ShowcaseRow>
      <ShowcaseRow label="Stack-Gaps">
        <div className="grid w-full gap-6 sm:grid-cols-2 lg:grid-cols-5">
          {STACK_GAPS.map((gap) => (
            <Stack key={gap} gap={gap} className="rounded-md border bg-muted/20 p-3">
              <span className="text-xs font-medium text-muted-foreground">gap={gap}</span>
              <div className="h-4 rounded bg-primary/30" />
              <div className="h-4 rounded bg-primary/30" />
              <div className="h-4 rounded bg-primary/30" />
            </Stack>
          ))}
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
