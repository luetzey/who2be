import { Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

import { useWorkAreaSearch } from '../hooks/useWorkAreaSearch'
import { useWorkAreas } from '../hooks/useWorkAreas'
import { splitAnchor } from '../lib/blocks'

export function WorkAreaSearchPage() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  // Der Suchzustand lebt in der URL (Bestandsmuster `useListFilters`): ein
  // Treffer ist damit teilbar und der Zurueck-Knopf fuehrt zurueck in die
  // Ergebnisliste, nicht auf eine leere Suche.
  const [params, setParams] = useSearchParams()
  const query = params.get('q') ?? ''
  const areaId = params.get('area') ?? ''
  const debounced = useDebouncedValue(query)
  const { hits, loading, error } = useWorkAreaSearch(debounced, areaId)
  const { areas } = useWorkAreas()

  const update = (next: { q?: string; area?: string }) => {
    const merged = new URLSearchParams(params)
    for (const [key, value] of Object.entries(next)) {
      if (value === '') merged.delete(key)
      else merged.set(key, value)
    }
    setParams(merged, { replace: true })
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader title={t('search.title')} description={t('search.description')} />
        <Card>
          <CardContent className="flex flex-wrap items-end gap-3 pt-6">
            <Label
              htmlFor="workarea-search"
              className="flex min-w-64 flex-1 flex-col items-start gap-1 text-sm font-normal"
            >
              <span className="font-medium">{t('search.label')}</span>
              <span className="relative w-full">
                <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="workarea-search"
                  value={query}
                  onChange={(e) => update({ q: e.target.value })}
                  placeholder={t('search.placeholder')}
                  className="pl-9"
                />
              </span>
            </Label>
            <Label
              htmlFor="workarea-search-area"
              className="flex flex-col items-start gap-1 text-sm font-normal"
            >
              <span className="font-medium">{t('search.areaLabel')}</span>
              <Select
                id="workarea-search-area"
                value={areaId}
                onChange={(e) => update({ area: e.target.value })}
              >
                <option value="">{t('search.areaAll')}</option>
                {areas.map((area) => (
                  <option key={area.id} value={area.id}>
                    {area.name}
                  </option>
                ))}
              </Select>
            </Label>
          </CardContent>
        </Card>
        {query.trim() === '' ? (
          <EmptyState
            icon={Search}
            title={t('search.promptTitle')}
            description={t('search.promptDescription')}
          />
        ) : (
          <DataView
            loading={loading}
            error={error}
            empty={hits.length === 0}
            emptyTitle={t('search.noResultsTitle')}
            emptyDescription={t('search.noResultsDescription', { query })}
          >
            <Stack gap="sm">
              <p className="text-xs text-muted-foreground">
                {t('search.resultCount', { count: hits.length })}
              </p>
              <ul className="flex flex-col gap-3">
                {hits.map((hit) => {
                  const parts = splitAnchor(hit.anchor)
                  return (
                    <li key={hit.anchor}>
                      <Card>
                        <CardContent className="flex flex-col gap-2 pt-6">
                          <Link
                            to={wsPath(
                              `/workarea/areas/${hit.area_id}/artifacts/${hit.artifact_id}#${parts?.blockId ?? hit.block_id}`,
                            )}
                            className="text-sm font-medium tracking-tight hover:underline"
                          >
                            {hit.title}
                          </Link>
                          <p className="text-sm text-muted-foreground">{hit.snippet}</p>
                          <span>
                            <MetaPill tone="muted">{hit.anchor}</MetaPill>
                          </span>
                        </CardContent>
                      </Card>
                    </li>
                  )
                })}
              </ul>
            </Stack>
          </DataView>
        )}
      </Stack>
    </Container>
  )
}
