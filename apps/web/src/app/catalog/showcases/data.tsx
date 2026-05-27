import { Users } from 'lucide-react'

import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

interface DemoItem {
  id: string
  name: string
  detail: string
}

const DEMO_ITEMS: readonly DemoItem[] = [
  { id: 'p1', name: 'backend-reviewer', detail: 'v1.2.0 · aktiv' },
  { id: 'p2', name: 'frontend-reviewer', detail: 'v0.4.0 · draft' },
  { id: 'p3', name: 'security-reviewer', detail: 'v2.0.1 · aktiv' },
]

export function DataShowcase() {
  return (
    <ShowcaseSection
      id="data"
      title="Data-Komponenten"
      description="DataList, DataView, EmptyState, ErrorAlert, LoadingState — standardisierte Render-States fuer asynchrone Listen."
    >
      <ShowcaseRow label="LoadingState">
        <div className="w-full max-w-md">
          <LoadingState rows={3} />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="ErrorAlert">
        <div className="w-full max-w-md">
          <ErrorAlert message="Beispiel-Fehlermeldung vom API-Layer (HTTP 500)." />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="EmptyState (mit Icon)">
        <div className="w-full max-w-md">
          <EmptyState
            icon={Users}
            title="Noch keine Personae"
            description="Lege deine erste Persona an, um loszulegen."
            action={
              <Button variant="brand" size="sm">
                Neue Persona
              </Button>
            }
          />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="DataList (befuellt)">
        <div className="w-full max-w-md">
          <DataList
            items={[...DEMO_ITEMS]}
            getKey={(item) => item.id}
            renderItem={(item) => (
              <div className="flex items-center justify-between">
                <span className="font-medium">{item.name}</span>
                <span className="text-xs text-muted-foreground">{item.detail}</span>
              </div>
            )}
          />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="DataView (befuellt)">
        <div className="w-full max-w-md">
          <DataView empty={false}>
            <p className="text-sm">DataView umschliesst Erfolgs-Inhalt und reicht States durch.</p>
          </DataView>
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="DataView (empty)">
        <div className="w-full max-w-md">
          <DataView
            empty
            emptyTitle="Keine Treffer"
            emptyDescription="Passe den Filter an oder lege einen Eintrag an."
          >
            {null}
          </DataView>
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
