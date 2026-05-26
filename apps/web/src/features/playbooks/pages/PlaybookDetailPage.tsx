import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { PlaybookEditorForm } from '../components/PlaybookEditorForm'
import { usePlaybook } from '../hooks/usePlaybook'
import { usePlaybookForm } from '../hooks/usePlaybookForm'

export function PlaybookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { playbook, versions, loading, error, reload } = usePlaybook(id)
  const { form, onSubmit, saveError } = usePlaybookForm(playbook, reload)

  if (id === undefined) {
    return <Navigate to="/playbooks" replace />
  }

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to="/playbooks">
            <ArrowLeft className="h-4 w-4" />
            Playbooks
          </Link>
        </Button>

        <DataView loading={loading && playbook === null} error={error}>
          {playbook !== null ? (
            <Stack gap="lg">
              <PageHeader
                title={playbook.name}
                description={`Aktuelle Version: ${playbook.current_version}`}
                actions={
                  playbook.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-1" aria-label="Tags">
                      {playbook.tags.map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  ) : undefined
                }
              />
              <PlaybookEditorForm form={form} onSubmit={onSubmit} saveError={saveError} />

              <Card>
                <CardHeader>
                  <CardTitle>Versionen</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataList
                    items={versions}
                    getKey={(version) => String(version.version)}
                    renderItem={(version) => (
                      <span>
                        v{version.version} — {new Date(version.created_at).toLocaleString()}
                      </span>
                    )}
                  />
                </CardContent>
              </Card>
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
