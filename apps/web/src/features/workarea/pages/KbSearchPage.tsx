import { Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

import { StatusBadge, TierBadge } from '../components/KbBadges'
import { useKbSearch } from '../hooks/useWorkAreaSearch'

export function KbSearchPage() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const debounced = useDebouncedValue(query)
  const { hits, loading, error } = useKbSearch(debounced)

  const setQuery = (value: string) => {
    const merged = new URLSearchParams(params)
    if (value === '') merged.delete('q')
    else merged.set('q', value)
    setParams(merged, { replace: true })
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader title={t('kb.title')} description={t('kb.description')} />
        <Card>
          <CardContent className="pt-6">
            <Label
              htmlFor="kb-search"
              className="flex flex-col items-start gap-1 text-sm font-normal"
            >
              <span className="font-medium">{t('kb.label')}</span>
              <span className="relative w-full">
                <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="kb-search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t('kb.placeholder')}
                  className="pl-9"
                />
              </span>
            </Label>
          </CardContent>
        </Card>
        {query.trim() === '' ? (
          <EmptyState
            icon={Search}
            title={t('kb.promptTitle')}
            description={t('kb.promptDescription')}
          />
        ) : (
          <DataView
            loading={loading}
            error={error}
            empty={hits.length === 0}
            emptyTitle={t('kb.noResultsTitle')}
            emptyDescription={t('kb.noResultsDescription', { query })}
          >
            <ul className="flex flex-col gap-3">
              {hits.map((hit) => (
                <li key={hit.node_id}>
                  <Card>
                    <CardContent className="flex flex-col gap-2 pt-6">
                      <span className="flex flex-wrap items-center gap-2">
                        <TierBadge tier={hit.tier} />
                        <StatusBadge status={hit.status} />
                      </span>
                      <Link
                        to={wsPath(`/workarea/kb/${hit.node_id}`)}
                        className="text-sm font-medium tracking-tight hover:underline"
                      >
                        {hit.snippet}
                      </Link>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          </DataView>
        )}
      </Stack>
    </Container>
  )
}
