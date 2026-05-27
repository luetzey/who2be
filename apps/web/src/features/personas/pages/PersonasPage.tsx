import { Plus, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { usePersonas } from '@/hooks/usePersonas'

export function PersonasPage() {
  const { personas, loading, error } = usePersonas()

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Personae"
          description="Versionierte Persona-Definitionen für deine Agenten."
          actions={
            <Button asChild variant="brand">
              <Link to="/personas/new">
                <Plus className="h-4 w-4" />
                Neue Persona
              </Link>
            </Button>
          }
        />
        <DataList
          items={personas}
          loading={loading}
          error={error}
          getKey={(persona) => persona.id}
          empty={
            <EmptyState
              icon={Users}
              title="Noch keine Personae"
              description="Lege deine erste Persona an, um Agenten zu konfigurieren."
              action={
                <Button asChild variant="brand">
                  <Link to="/personas/new">
                    <Plus className="h-4 w-4" />
                    Neue Persona
                  </Link>
                </Button>
              }
            />
          }
          renderItem={(persona) => (
            <div className="flex items-center justify-between gap-3">
              <Link
                to={`/personas/${persona.id}`}
                className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                {persona.name}
              </Link>
              <Badge variant="secondary">v{persona.current_version}</Badge>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
