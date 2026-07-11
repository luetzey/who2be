import { GitBranch, Pencil } from 'lucide-react'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function TabsShowcase() {
  return (
    <ShowcaseSection
      id="tabs"
      title="Tabs"
      description="Underline-Tab-Leiste fuer Detail-Pages. ARIA-Tabs-Pattern (roving tabindex, Pfeil-Navigation), aktiver 2px-Brand-Unterstrich."
    >
      <ShowcaseRow label="Detail-Tabs">
        <div className="w-full max-w-md">
          <Tabs defaultValue="edit">
            <TabsList aria-label="Beispiel-Tabs">
              <TabsTrigger value="edit">
                <Pencil aria-hidden="true" />
                Bearbeiten
              </TabsTrigger>
              <TabsTrigger value="versions">
                <GitBranch aria-hidden="true" />
                Versionen
              </TabsTrigger>
            </TabsList>
            <TabsContent value="edit">
              <p className="text-sm text-muted-foreground">Editor-Panel (aktiv).</p>
            </TabsContent>
            <TabsContent value="versions">
              <p className="text-sm text-muted-foreground">Versionshistorie-Panel.</p>
            </TabsContent>
          </Tabs>
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
