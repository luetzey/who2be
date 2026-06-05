import { BookOpen, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

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
  const { t } = useTranslation('playbooks')
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
            title={t('list.title')}
            description={t('list.description')}
            actions={
              <Button asChild variant="brand">
                <Link to={wsPath("/playbooks/new")}>
                  <Plus className="h-4 w-4" />
                  {t('list.newButton')}
                </Link>
              </Button>
            }
          />
          <Card>
            <CardContent className="grid gap-4 pt-6 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbook-tag-filter">{t('list.tagFilter')}</Label>
                <Input
                  id="playbook-tag-filter"
                  value={tagFilter}
                  onChange={(event) => setTagFilter(event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbook-trigger-filter">{t('list.triggerFilter')}</Label>
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
                    ? t('list.empty.title')
                    : t('list.empty.filteredTitle')
                }
                description={
                  playbooks.length === 0
                    ? t('list.empty.description')
                    : t('list.empty.filteredDescription')
                }
                action={
                  <Button asChild variant="brand">
                    <Link to={wsPath("/playbooks/new")}>
                      <Plus className="h-4 w-4" />
                      {t('list.newButton')}
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
                  <div className="flex flex-wrap gap-1" aria-label={t('common:fields.tags')}>
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
