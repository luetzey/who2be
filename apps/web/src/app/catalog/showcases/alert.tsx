import { AlertTriangle, Info } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function AlertShowcase() {
  return (
    <ShowcaseSection
      id="alert"
      title="Alert"
      description="Inline-Hinweis fuer kritische, dauerhaft sichtbare Information. Fluechtige UX-Meldungen → Toast (notify.*)."
    >
      <ShowcaseRow label="Default">
        <Alert className="max-w-md">
          <Info />
          <AlertTitle>Hinweis</AlertTitle>
          <AlertDescription>Diese Aenderung wird mit dem naechsten Push aktiv.</AlertDescription>
        </Alert>
      </ShowcaseRow>
      <ShowcaseRow label="Destructive">
        <Alert variant="destructive" className="max-w-md">
          <AlertTriangle />
          <AlertTitle>Fehler beim Speichern</AlertTitle>
          <AlertDescription>Der Server hat die Anfrage abgelehnt (HTTP 409).</AlertDescription>
        </Alert>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
