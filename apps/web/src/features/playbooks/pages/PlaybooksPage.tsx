import { BookOpen, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { usePlaybooks } from '@/hooks/usePlaybooks'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

export function PlaybooksPage() {
  const { playbooks, loading, error } = usePlaybooks()
  const wsPath = useWorkspacePath()
  const [tagFilter, setTagFilter] = useState('')
  const [triggerFilter, setTriggerFilter] = useState('')

  const filtered = useMemo(() => {
    const tag = tagFilter.trim().toLowerCase()
    const trigger = triggerFilter.trim().toLowerCase()
    return playbooks.filter((playbook) => {
      const tagMatch =
        tag === '' || playbook.tags.some((entry) => entry.toLowerCase().includes(tag))
      const triggerMatch =
        trigger === '' || (playbook.triggers ?? '').toLowerCase().includes(trigger)
      return tagMatch && triggerMatch
    })
  }, [playbooks, tagFilter, triggerFilter])

  return (
    <Container>
        <Stack gap="lg">
          <PageHeader
            title="Playbooks"
            description="Workflows und Playbook-Versionen für Agenten."
            actions={
              <Button asChild variant="brand">
                <Link to={wsPath("/playbooks/new")}>
                  <Plus className="h-4 w-4" />
                  Neues Playbook
                </Link>
              </Button>
            }
          />
          <Card>
            <CardContent className="grid gap-4 pt-6 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbook-tag-filter">Tag-Filter</Label>
                <Input
                  id="playbook-tag-filter"
                  value={tagFilter}
                  onChange={(event) => setTagFilter(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbook-trigger-filter">Trigger-Filter</Label>
                <Input
                  id="playbook-trigger-filter"
                  value={triggerFilter}
                  onChange={(event) => setTriggerFilter(event.target.value)}
                />
              </div>
            </CardContent>
          </Card>

          <DataList
            items={filtered}
            loading={loading}
            error={error}
            getKey={(playbook) => playbook.id}
            empty={
              <EmptyState
                icon={BookOpen}
                title={
                  playbooks.length === 0
                    ? 'Noch keine Playbooks'
                    : 'Keine Playbooks für diesen Filter'
                }
                description={
                  playbooks.length === 0
                    ? 'Lege dein erstes Playbook an, um Workflows zu definieren.'
                    : 'Passe Tag- oder Trigger-Filter an oder lege ein neues Playbook an.'
                }
                action={
                  <Button asChild variant="brand">
                    <Link to={wsPath("/playbooks/new")}>
                      <Plus className="h-4 w-4" />
                      Neues Playbook
                    </Link>
                  </Button>
                }
              />
            }
            renderItem={(playbook) => (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Link
                    to={wsPath(`/playbooks/${playbook.id}`)}
                    className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                  >
                    {playbook.name}
                  </Link>
                  <span className="text-xs text-muted-foreground">
                    {playbook.type} · v{playbook.current_version}
                  </span>
                </div>
                {playbook.tags.length > 0 ? (
                  <div className="flex flex-wrap gap-1" aria-label="Tags">
                    {playbook.tags.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            )}
          />
        </Stack>
    </Container>
  )
}
