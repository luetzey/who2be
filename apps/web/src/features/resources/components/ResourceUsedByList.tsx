// ResourceUsedByList — read-only Backlinks aus GET /resources/{id}/used_by.
// Zeigt welche Resources diese Resource als Sub-Resource fuehren (Track E §3.3).
// Delegiert an die geteilte `UsedByList` (Muster: ComposedByList).

import { useTranslation } from 'react-i18next'

import type { ResourceRef } from '@/api/types'
import { UsedByList } from '@/components/data/UsedByList'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

interface ResourceUsedByListProps {
  parents: ResourceRef[]
}

export function ResourceUsedByList({ parents }: ResourceUsedByListProps) {
  const { t } = useTranslation('resources')
  const wsPath = useWorkspacePath()

  return (
    <UsedByList
      aria-label={t('usedBy.ariaLabel')}
      items={parents.map((parent) => ({
        id: parent.id,
        name: parent.name,
        href: wsPath(`/resources/${parent.id}`),
      }))}
      empty={<p className="text-sm text-muted-foreground">{t('usedBy.empty')}</p>}
    />
  )
}
