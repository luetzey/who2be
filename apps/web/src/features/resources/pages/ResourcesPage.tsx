import { FileText, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { Resource } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useResources } from '@/hooks/useResources'

export function ResourcesPage() {
  const { resources, loading, error } = useResources()
  const wsPath = useWorkspacePath()
  const [activeTag, setActiveTag] = useState<string | null>(null)

  // Client-seitiger Tag-Filter — einfach und ohne extra API-Call fuer die Listenseite.
  // Bei grossen Workspaces kann spaeter auf GET /resources?tag= umgestellt werden.
  const filtered: Resource[] =
    activeTag === null
      ? resources
      : resources.filter((r) => (r.content.tags ?? []).includes(activeTag))

  // Alle vorhandenen Tags aus der geladenen Liste sammeln.
  const allTags = Array.from(
    new Set(resources.flatMap((r) => r.content.tags ?? [])),
  ).sort()

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

        {allTags.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Tag-Filter">
            <span className="text-xs font-medium text-muted-foreground">Tags:</span>
            {allTags.map((tag) => (
              <Badge
                key={tag}
                variant={activeTag === tag ? 'default' : 'outline'}
                className="cursor-pointer select-none"
                onClick={() => setActiveTag(activeTag === tag ? null : tag)}
                role="button"
                aria-pressed={activeTag === tag}
              >
                {tag}
              </Badge>
            ))}
            {activeTag !== null ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 gap-1 px-2 text-xs"
                onClick={() => setActiveTag(null)}
              >
                <X className="size-3" />
                Filter zurücksetzen
              </Button>
            ) : null}
          </div>
        ) : null}

        <DataList
          items={filtered}
          loading={loading}
          error={error}
          getKey={(resource) => resource.id}
          empty={
            activeTag !== null ? (
              <EmptyState
                icon={FileText}
                title={`Keine Resources mit Tag „${activeTag}"`}
                description="Entferne den Filter oder lege eine neue Resource mit diesem Tag an."
                action={
                  <Button type="button" variant="outline" onClick={() => setActiveTag(null)}>
                    Filter zurücksetzen
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={FileText}
                title="Noch keine Resources"
                description="Lege deine erste Resource an, um Wissen in Blöcken zu erfassen."
                action={
                  <Button asChild variant="brand">
                    <Link to={wsPath('/resources/new')}>
                      <Plus className="h-4 w-4" />
                      Neue Resource
                    </Link>
                  </Button>
                }
              />
            )
          }
          renderItem={(resource) => (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={wsPath(`/resources/${resource.id}`)}
                  className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                >
                  {resource.name}
                </Link>
                {(resource.content.tags ?? []).length > 0 ? (
                  <div className="flex flex-wrap gap-1" aria-label="Tags">
                    {(resource.content.tags ?? []).map((tag) => (
                      <Badge
                        key={tag}
                        variant={activeTag === tag ? 'default' : 'secondary'}
                        className="cursor-pointer text-xs"
                        onClick={(e) => {
                          e.preventDefault()
                          setActiveTag(activeTag === tag ? null : tag)
                        }}
                        role="button"
                        aria-pressed={activeTag === tag}
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
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
