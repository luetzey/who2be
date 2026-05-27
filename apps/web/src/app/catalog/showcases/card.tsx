import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function CardShowcase() {
  return (
    <ShowcaseSection
      id="card"
      title="Card"
      description="Container fuer abgegrenzte Inhaltsbloecke. Slots: Header, Title, Description, Content, Footer."
    >
      <ShowcaseRow label="Vollstaendig">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Persona</CardTitle>
            <CardDescription>Senior Backend Engineer</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Spezialisierung auf API-Design, Datenbank-Optimierung und Observability.
          </CardContent>
          <CardFooter className="justify-end gap-2">
            <Button variant="ghost" size="sm">
              Abbrechen
            </Button>
            <Button size="sm">Speichern</Button>
          </CardFooter>
        </Card>
      </ShowcaseRow>
      <ShowcaseRow label="Nur Content">
        <Card className="max-w-sm">
          <CardContent className="text-sm">Minimaler Card-Inhalt ohne Header/Footer.</CardContent>
        </Card>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
