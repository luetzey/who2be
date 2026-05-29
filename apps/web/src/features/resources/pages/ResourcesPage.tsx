import { FileText, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Button } from '@/components/ui/button'
import { useResources } from '@/hooks/useResources'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

export function ResourcesPage() {
  const { resources, loading, error } = useResources()
  const wsPath = useWorkspacePath()

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Resources"
          description="Versionierte Wissensbausteine mit Block-Editor."
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/resources/new')}>
                <Plus className="h-4 w-4" />
                Neue Resource
              </Link>
            </Button>
          }
        />

        <DataList
          items={resources}
          loading={loading}
          error={error}
          getKey={(resource) => resource.id}
          empty={
            <EmptyState
              icon={FileText}
              title="Noch keine Resources"
              description="Lege deine erste Resource an, um Wissen in Bloecken zu erfassen."
              action={
                <Button asChild variant="brand">
                  <Link to={wsPath('/resources/new')}>
                    <Plus className="h-4 w-4" />
                    Neue Resource
                  </Link>
                </Button>
              }
            />
          }
          renderItem={(resource) => (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Link
                to={wsPath(`/resources/${resource.id}`)}
                className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                {resource.name}
              </Link>
              <span className="text-xs text-muted-foreground">
                v{resource.current_version}
              </span>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
