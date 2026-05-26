import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataList } from '@/components/data/DataList'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useSession } from '@/auth/session-context'
import { usePersonas } from '@/hooks/usePersonas'

export function PersonasPage() {
  const { personas, loading, error } = usePersonas()
  const { signOut } = useSession()

  return (
    <AppShell onSignOut={() => void signOut()}>
      <Container>
        <PageHeader
          title="Personae"
          description="Versionierte Persona-Definitionen fuer deine Agenten."
          actions={
            <Button asChild>
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
          renderItem={(persona) => (
            <div className="flex items-center justify-between gap-3">
              <Link
                to={`/personas/${persona.id}`}
                className="font-medium text-foreground hover:underline"
              >
                {persona.name}
              </Link>
              <Badge variant="secondary">v{persona.current_version}</Badge>
            </div>
          )}
        />
      </Container>
    </AppShell>
  )
}
